from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from io import BytesIO

from .models import Property, Reservation, SavedProperty, VisitRequest
from .repository import (
    create_property,
    create_reservation,
    create_visit,
    get_property,
    list_properties,
)

User = get_user_model()


class RentalWorkflowTests(TestCase):
    def setUp(self):
        self.renter = self.make_user("renter", User.Role.RENTER)
        self.landlord = self.make_user("landlord", User.Role.LANDLORD)
        self.other_landlord = self.make_user("other", User.Role.LANDLORD)
        self.listing = self.make_property("Garden apartment", Property.Status.PUBLISHED)
        self.draft = self.make_property("Private draft", Property.Status.DRAFT)

    @staticmethod
    def make_user(username, role):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="test-password-123",
            first_name=username.title(),
            last_name="User",
            role=role,
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
            self.landlord.pk,
        )

    def login(self, user):
        self.client.force_login(user)

    def test_django_search_filters_and_hides_drafts(self):
        response = self.client.get(
            reverse("home"), {"city": "pune", "max_rent": "26000"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Garden apartment")
        self.assertNotContains(response, "Private draft")
        self.assertEqual(
            len(list_properties(status=Property.Status.PUBLISHED)),
            1,
        )

    def test_homepage_shows_published_listings_without_search_filters(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Garden apartment")
        self.assertNotContains(response, "Private draft")

    def test_listing_keyword_search_matches_property_details(self):
        response = self.client.get(reverse("listings"), {"q": "bright apartment"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Garden apartment")
        self.assertContains(response, "Keyword")
        self.assertNotContains(response, "Private draft")

    def test_contact_form_sends_validated_message_to_configured_inbox(self):
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            DEFAULT_FROM_EMAIL="noreply@example.com",
            CONTACT_EMAIL="support@example.com",
        ):
            response = self.client.post(
                reverse("contact"),
                {
                    "name": "Alex Seeker",
                    "email": "alex@example.com",
                    "subject": "Question about a listing",
                    "message": "Could you tell me more about this place?",
                    "website": "",
                },
            )

        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["support@example.com"])
        self.assertIn("alex@example.com", mail.outbox[0].body)

    def test_contact_form_rejects_multiline_subject(self):
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            DEFAULT_FROM_EMAIL="noreply@example.com",
            CONTACT_EMAIL="support@example.com",
        ):
            response = self.client.post(
                reverse("contact"),
                {
                    "name": "Alex Seeker",
                    "email": "alex@example.com",
                    "subject": "Question\r\nBcc: other@example.com",
                    "message": "Could you tell me more about this place?",
                    "website": "",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a subject on a single line.")

    def test_invalid_search_does_not_return_all_properties(self):
        response = self.client.get(
            reverse("home"), {"min_rent": "40000", "max_rent": "10000"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maximum rent must be at least the minimum rent.")
        self.assertNotContains(response, "Garden apartment")

    def test_login_uses_django_auth_and_enforces_account_role(self):
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

        response = self.client.post(
            reverse("login"),
            {
                "username": "renter",
                "password": "test-password-123",
                "role": User.Role.RENTER,
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertIn("sessionid", self.client.cookies)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_logout_clears_the_django_session(self):
        self.login(self.renter)
        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_signup_persists_django_user_and_logs_it_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new-owner",
                "email": "NEW-OWNER@example.com",
                "first_name": "New",
                "last_name": "Owner",
                "role": User.Role.LANDLORD,
                "password1": "secure-test-password",
                "password2": "secure-test-password",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="new-owner")
        self.assertEqual(user.email, "new-owner@example.com")
        self.assertEqual(user.role, User.Role.LANDLORD)
        self.assertTrue(user.check_password("secure-test-password"))
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_signup_rejects_passwords_shorter_than_eight_characters(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "short-password-user",
                "email": "short-password@example.com",
                "first_name": "Short",
                "last_name": "Password",
                "role": User.Role.RENTER,
                "password1": "123",
                "password2": "123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "at least 8 characters")
        self.assertFalse(User.objects.filter(username="short-password-user").exists())

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
        self.assertEqual(get_property(self.draft.pk).status, Property.Status.PUBLISHED)

    def test_provider_dashboard_uses_supported_listing_status_actions(self):
        self.login(self.landlord)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Garden apartment")
        self.assertContains(response, "Pause")
        self.assertContains(response, "Publish")
        self.assertContains(response, "Booking requests")
        self.assertContains(response, "Visit requests")

    def test_renter_can_save_and_remove_a_listing(self):
        self.login(self.renter)
        detail = self.client.get(reverse("property_detail", args=[self.listing.pk]))
        self.assertEqual(detail.status_code, 200)
        save_action = reverse("saved_property_toggle", args=[self.listing.pk])
        booking_action = reverse("reservation_create", args=[self.listing.pk])
        visit_action = reverse("visit_request_create", args=[self.listing.pk])
        self.assertContains(detail, f'action="{save_action}"')
        self.assertContains(detail, f'action="{booking_action}"')
        self.assertContains(detail, f'action="{visit_action}"')

        response = self.client.post(save_action, {"action": "save"})
        self.assertRedirects(response, reverse("property_detail", args=[self.listing.pk]))
        self.assertEqual(SavedProperty.objects.filter(renter=self.renter).count(), 1)
        self.assertContains(self.client.get(reverse("dashboard")), "Garden apartment")

        response = self.client.post(save_action, {"action": "remove"})
        self.assertRedirects(response, reverse("property_detail", args=[self.listing.pk]))
        self.assertEqual(SavedProperty.objects.count(), 0)

    def test_renter_visit_request_is_validated_and_unique_while_open(self):
        self.login(self.renter)
        visit_time = timezone.now() + timedelta(days=2)
        response = self.client.post(
            reverse("visit_request_create", args=[self.listing.pk]),
            {
                "scheduled_for": timezone.localtime(visit_time)
                .replace(second=0, microsecond=0)
                .strftime("%Y-%m-%dT%H:%M"),
                "message": "After work",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))

        duplicate_time = timezone.now() + timedelta(days=3)
        response = self.client.post(
            reverse("visit_request_create", args=[self.listing.pk]),
            {
                "scheduled_for": timezone.localtime(duplicate_time)
                .replace(second=0, microsecond=0)
                .strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already have an open visit request")
        visit = VisitRequest.objects.get()
        self.assertEqual(visit.status, VisitRequest.Status.REQUESTED)

        renter_dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(renter_dashboard, "Cancel")
        self.login(self.landlord)
        provider_dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(provider_dashboard, "Requested by Renter User")
        self.assertContains(provider_dashboard, "Confirm")
        self.assertContains(
            provider_dashboard,
            f'action="{reverse("visit_request_decide", args=[visit.pk])}"',
        )

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
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.status, Reservation.Status.REQUESTED)

        with self.assertRaisesRegex(ValueError, "overlap another active"):
            create_reservation(
                self.listing.pk,
                self.renter.pk,
                start + timedelta(days=1),
                end + timedelta(days=1),
            )

        self.login(self.renter)
        renter_dashboard = self.client.get(reverse("dashboard"))
        cancel_action = reverse("reservation_cancel", args=[reservation.pk])
        self.assertContains(renter_dashboard, f'action="{cancel_action}"')

        self.login(self.landlord)
        provider_dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(provider_dashboard, "Requested stay")
        decision_action = reverse("reservation_decide", args=[reservation.pk])
        self.assertContains(provider_dashboard, f'action="{decision_action}"')
        response = self.client.post(
            decision_action,
            {"status": Reservation.Status.CONFIRMED},
        )
        self.assertRedirects(response, reverse("dashboard"))
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)

        self.login(self.renter)
        self.assertContains(
            self.client.get(reverse("dashboard")),
            f'action="{cancel_action}"',
        )

    def test_public_user_cannot_open_private_draft(self):
        response = self.client.get(reverse("property_detail", args=[self.draft.pk]))
        self.assertEqual(response.status_code, 404)

    @staticmethod
    def image_upload(name):
        image_buffer = BytesIO()
        Image.new("RGB", (12, 12), color="forestgreen").save(
            image_buffer, format="PNG"
        )
        return SimpleUploadedFile(
            name,
            image_buffer.getvalue(),
            content_type="image/png",
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
                        "status": Property.Status.PUBLISHED,
                        "additional_images": [
                            self.image_upload("room.png"),
                            self.image_upload("balcony.png"),
                        ],
                    },
                )

                self.assertRedirects(response, reverse("dashboard"))
                property_listing = Property.objects.get(title="Room with balcony")
                images = property_listing.gallery_images
                self.assertEqual(len(images), 2)
                self.assertTrue(
                    all((Path(media_directory) / image.image.name).is_file() for image in images)
                )

                detail = self.client.get(
                    reverse("property_detail", args=[property_listing.pk])
                )
                self.assertEqual(detail.status_code, 200)
                self.assertContains(detail, "room.png")

                removed_image = images[0]
                response = self.client.post(
                    reverse(
                        "property_image_delete",
                        args=[property_listing.pk, removed_image.image_id],
                    )
                )
                self.assertRedirects(
                    response,
                    reverse("property_edit", args=[property_listing.pk]),
                )
                property_listing.refresh_from_db()
                self.assertEqual(len(property_listing.gallery_images), 1)
                self.assertFalse(
                    (Path(media_directory) / removed_image.image.name).exists()
                )

    def test_provider_cannot_create_a_listing_as_a_renter(self):
        self.login(self.renter)

        response = self.client.get(reverse("property_create"))

        self.assertRedirects(response, reverse("dashboard"))

    def test_visit_request_can_be_confirmed_and_cancelled(self):
        visit = create_visit(
            self.listing.pk,
            self.renter.pk,
            timezone.now() + timedelta(days=2),
        )
        self.login(self.landlord)
        response = self.client.post(
            reverse("visit_request_decide", args=[visit.pk]),
            {"status": VisitRequest.Status.CONFIRMED},
        )
        self.assertRedirects(response, reverse("dashboard"))
        visit.refresh_from_db()
        self.assertEqual(visit.status, VisitRequest.Status.CONFIRMED)

        self.login(self.renter)
        response = self.client.post(
            reverse("visit_request_cancel", args=[visit.pk])
        )
        self.assertRedirects(response, reverse("dashboard"))
        visit.refresh_from_db()
        self.assertEqual(visit.status, VisitRequest.Status.CANCELLED)
