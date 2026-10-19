from io import BytesIO
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import signing
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .middleware import AUTH_COOKIE_NAME, AUTH_COOKIE_SALT
from .models import Property, Reservation, User, VisitRequest
from .repository import (
    create_property,
    create_reservation,
    create_user,
    create_visit,
    database,
    ensure_indexes,
    get_property,
    get_reservation,
    get_user,
    get_visit,
    list_properties,
    update_reservation_status,
)


class RentalWorkflowTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.database_name = f"renthouse_test_{uuid4().hex}"
        cls.mongo_settings = override_settings(MONGODB_DATABASE=cls.database_name)
        cls.mongo_settings.enable()

    @classmethod
    def tearDownClass(cls):
        database().client.drop_database(settings.MONGODB_DATABASE)
        cls.mongo_settings.disable()
        super().tearDownClass()

    def setUp(self):
        database().client.drop_database(settings.MONGODB_DATABASE)
        ensure_indexes(force=True)
        self.renter = self.make_user("renter", User.Role.RENTER)
        self.landlord = self.make_user("landlord", User.Role.LANDLORD)
        self.other_landlord = self.make_user("other", User.Role.LANDLORD)
        self.listing = self.make_property("Garden apartment", Property.Status.PUBLISHED)
        self.draft = self.make_property("Private draft", Property.Status.DRAFT)

    @staticmethod
    def make_user(username, role):
        return create_user(
            username=username,
            email=f"{username}@example.com",
            first_name=username.title(),
            last_name="User",
            role=role,
            password_hash=make_password("test-password-123"),
        )

    def make_property(self, title, status):
        return create_property(
            {
                "title": title,
                "description": "A bright apartment near the park.",
                "property_type": Property.PropertyType.APARTMENT,
                "monthly_rent": Decimal("25000"),
                "security_deposit": Decimal("50000"),
                "address": "10 Green Road",
                "city": "Pune",
                "state": "Maharashtra",
                "postal_code": "411001",
                "bedrooms": 2,
                "bathrooms": 1,
                "available_from": timezone.localdate(),
                "status": status,
            },
            self.landlord.id,
        )

    def login(self, user):
        self.client.cookies[AUTH_COOKIE_NAME] = signing.dumps(
            user.id, salt=AUTH_COOKIE_SALT
        )

    def test_mongodb_search_filters_and_hides_drafts(self):
        response = self.client.get(reverse("home"), {"city": "pune", "max_rent": "26000"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Garden apartment")
        self.assertNotContains(response, "Private draft")
        self.assertEqual(len(list_properties(status=Property.Status.PUBLISHED)), 1)

    def test_homepage_shows_published_listings_without_search_filters(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Garden apartment")
        self.assertNotContains(response, "Private draft")

    def test_invalid_search_does_not_return_all_properties(self):
        response = self.client.get(
            reverse("home"), {"min_rent": "40000", "max_rent": "10000"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maximum rent must be at least the minimum rent.")
        self.assertNotContains(response, "Garden apartment")

    def test_user_authentication_uses_signed_cookie_and_enforces_role(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "renter",
                "password": "test-password-123",
                "role": User.Role.LANDLORD,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid credentials for the selected account type")
        self.assertNotIn(AUTH_COOKIE_NAME, self.client.cookies)

        response = self.client.post(
            reverse("login"),
            {
                "username": "renter",
                "password": "test-password-123",
                "role": User.Role.RENTER,
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertIn(AUTH_COOKIE_NAME, self.client.cookies)
        self.assertEqual(get_user(self.renter.id).id, self.renter.id)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_logout_clears_the_authentication_cookie(self):
        self.login(self.renter)
        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(response.cookies[AUTH_COOKIE_NAME].value, "")

    def test_signup_persists_account_in_mongodb_and_logs_it_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new-owner",
                "email": "NEW-OWNER@example.com",
                "first_name": "New",
                "last_name": "Owner",
                "role": User.Role.LANDLORD,
                "password1": "123",
                "password2": "123",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        user_doc = database().users.find_one({"username_lower": "new-owner"})
        self.assertIsNotNone(user_doc)
        self.assertEqual(user_doc["email"], "new-owner@example.com")
        self.assertEqual(user_doc["role"], User.Role.LANDLORD)

    def test_owner_can_publish_draft_but_another_owner_cannot_edit_it(self):
        self.login(self.other_landlord)
        response = self.client.get(reverse("property_edit", args=[self.draft.pk]))
        self.assertEqual(response.status_code, 404)

        self.login(self.landlord)
        response = self.client.post(
            reverse("property_status_update", args=[self.draft.pk]),
            {"status": Property.Status.PUBLISHED},
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(
            get_property(self.draft.pk).status, Property.Status.PUBLISHED
        )

    def test_renter_can_save_and_remove_a_listing(self):
        self.login(self.renter)
        save_url = reverse("saved_property_toggle", args=[self.listing.pk])
        response = self.client.post(save_url, {"action": "save"})

        self.assertRedirects(response, reverse("property_detail", args=[self.listing.pk]))
        self.assertEqual(
            database().saved_properties.count_documents(
                {"renter_id": database().users.find_one({"username": "renter"})["_id"]}
            ),
            1,
        )
        self.assertContains(self.client.get(reverse("dashboard")), "Garden apartment")

        response = self.client.post(save_url, {"action": "remove"})
        self.assertRedirects(response, reverse("property_detail", args=[self.listing.pk]))
        self.assertEqual(database().saved_properties.count_documents({}), 0)

    def test_renter_visit_request_is_validated_and_unique_while_open(self):
        self.login(self.renter)
        visit_time = timezone.now() + timedelta(days=2)
        response = self.client.post(
            reverse("visit_request_create", args=[self.listing.pk]),
            {
                "scheduled_for": timezone.localtime(visit_time).replace(
                    second=0, microsecond=0
                ).strftime("%Y-%m-%dT%H:%M"),
                "message": "After work",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))

        duplicate_time = timezone.now() + timedelta(days=3)
        response = self.client.post(
            reverse("visit_request_create", args=[self.listing.pk]),
            {
                "scheduled_for": timezone.localtime(duplicate_time).replace(
                    second=0, microsecond=0
                ).strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already have an open visit request")
        visit = get_visit(database().visit_requests.find_one()["_id"])
        self.assertEqual(visit.status, VisitRequest.Status.REQUESTED)

    def test_reservation_conflicts_are_rejected_and_decisions_persist(self):
        self.login(self.renter)
        start = timezone.localdate() + timedelta(days=5)
        end = start + timedelta(days=10)
        response = self.client.post(
            reverse("reservation_create", args=[self.listing.pk]),
            {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "message": "Please confirm",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        record = database().reservations.find_one()
        reservation = get_reservation(record["_id"])
        self.assertEqual(reservation.status, Reservation.Status.REQUESTED)

        with self.assertRaisesRegex(ValueError, "overlap another active"):
            create_reservation(
                self.listing.pk,
                self.renter.id,
                start + timedelta(days=1),
                end + timedelta(days=1),
            )

        self.login(self.landlord)
        response = self.client.post(
            reverse("reservation_decide", args=[reservation.pk]),
            {"status": Reservation.Status.CONFIRMED},
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(
            get_reservation(reservation.pk).status, Reservation.Status.CONFIRMED
        )

    def test_public_user_cannot_open_private_draft(self):
        response = self.client.get(
            reverse("property_detail", args=[self.draft.pk])
        )
        self.assertEqual(response.status_code, 404)

    @staticmethod
    def image_upload(name):
        image_buffer = BytesIO()
        Image.new("RGB", (12, 12), color="forestgreen").save(
            image_buffer, format="PNG"
        )
        return SimpleUploadedFile(
            name, image_buffer.getvalue(), content_type="image/png"
        )

    def test_provider_can_create_listing_with_gallery_images(self):
        self.login(self.landlord)
        with TemporaryDirectory() as media_directory:
            with override_settings(MEDIA_ROOT=media_directory):
                response = self.client.post(
                    reverse("property_create"),
                    {
                        "title": "Room with balcony",
                        "description": "Sunny room near transit.",
                        "property_type": Property.PropertyType.PG,
                        "monthly_rent": "18000",
                        "security_deposit": "18000",
                        "address": "5 Lake Road",
                        "city": "Pune",
                        "state": "Maharashtra",
                        "postal_code": "411004",
                        "bedrooms": "1",
                        "bathrooms": "1",
                        "available_from": timezone.localdate().isoformat(),
                        "status": Property.Status.DRAFT,
                        "additional_images": [
                            self.image_upload("room.png"),
                            self.image_upload("balcony.png"),
                        ],
                    },
                )

                self.assertRedirects(response, reverse("dashboard"))
                property_doc = database().properties.find_one(
                    {"title": "Room with balcony"}
                )
                self.assertIsNotNone(property_doc)
                images = list(
                    database().property_images.find(
                        {"property_id": property_doc["_id"]}
                    )
                )
                self.assertEqual(len(images), 2)
                self.assertTrue(
                    all((Path(media_directory) / image["image"]).is_file() for image in images)
                )

                detail = self.client.get(
                    reverse("property_detail", args=[str(property_doc["_id"])])
                )
                self.assertEqual(detail.status_code, 200)
                self.assertContains(detail, "room.png")
