from io import BytesIO
from datetime import timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Property, PropertyImage, SavedProperty, User, VisitRequest


class RentalWorkflowTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

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

    @classmethod
    def setUpTestData(cls):
        cls.renter = User.objects.create_user(
            username="renter",
            email="renter@example.com",
            password="Strong-pass-123!",
            role=User.Role.RENTER,
        )
        cls.landlord = User.objects.create_user(
            username="landlord",
            email="landlord@example.com",
            password="Strong-pass-123!",
            role=User.Role.LANDLORD,
        )
        cls.other_landlord = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="Strong-pass-123!",
            role=User.Role.LANDLORD,
        )
        cls.listing = Property.objects.create(
            owner=cls.landlord,
            title="Garden apartment",
            description="A bright apartment near the park.",
            property_type=Property.PropertyType.APARTMENT,
            monthly_rent=Decimal("25000"),
            security_deposit=Decimal("50000"),
            address="10 Green Road",
            city="Pune",
            state="Maharashtra",
            postal_code="411001",
            status=Property.Status.PUBLISHED,
        )
        cls.draft = Property.objects.create(
            owner=cls.landlord,
            title="Private draft",
            description="Not yet public.",
            property_type=Property.PropertyType.HOUSE,
            monthly_rent=Decimal("30000"),
            security_deposit=Decimal("30000"),
            address="20 Green Road",
            city="Pune",
            state="Maharashtra",
            postal_code="411002",
        )

    def test_public_search_only_shows_published_listings_and_applies_filters(self):
        response = self.client.get(reverse("home"), {"city": "pune", "max_rent": "26000"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Garden apartment")
        self.assertNotContains(response, "Private draft")

    def test_invalid_search_does_not_fall_back_to_all_listings(self):
        response = self.client.get(
            reverse("home"), {"min_rent": "40000", "max_rent": "10000"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maximum rent must be at least the minimum rent.")
        self.assertNotContains(response, "Garden apartment")

    def test_search_filters_bedrooms_and_move_in_date(self):
        future_listing = Property.objects.create(
            owner=self.landlord,
            title="Future three bedroom",
            description="Available next month.",
            property_type=Property.PropertyType.HOUSE,
            monthly_rent=Decimal("35000"),
            security_deposit=Decimal("35000"),
            address="22 Green Road",
            city="Pune",
            state="Maharashtra",
            postal_code="411003",
            bedrooms=3,
            available_from=timezone.localdate() + timedelta(days=20),
            status=Property.Status.PUBLISHED,
        )
        response = self.client.get(
            reverse("home"),
            {
                "min_bedrooms": "3",
                "move_in_date": (timezone.localdate() + timedelta(days=10)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, future_listing.title)
        self.assertNotContains(response, self.listing.title)

        response = self.client.get(
            reverse("home"),
            {
                "min_bedrooms": "3",
                "move_in_date": (timezone.localdate() + timedelta(days=30)).isoformat(),
            },
        )

        self.assertContains(response, future_listing.title)

    def test_anonymous_user_cannot_open_draft_listing(self):
        response = self.client.get(
            reverse("property_detail", args=[self.draft.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_public_listing_page_has_mobile_viewing_action(self):
        response = self.client.get(
            reverse("property_detail", args=[self.listing.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log in to request a viewing")

    def test_landlord_cannot_edit_another_landlords_listing(self):
        self.client.force_login(self.other_landlord)

        response = self.client.get(
            reverse("property_edit", args=[self.listing.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_service_provider_can_create_listing_with_multiple_photos(self):
        self.client.force_login(self.landlord)
        listing_form = self.client.get(reverse("property_create"))
        self.assertEqual(listing_form.status_code, 200)
        self.assertContains(listing_form, 'name="additional_images"')
        self.assertContains(listing_form, "multiple")

        response = self.client.post(
            reverse("property_create"),
            {
                "title": "Room with balcony",
                "description": "Sunny furnished room close to transit.",
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
        property_listing = Property.objects.get(title="Room with balcony")
        self.assertEqual(
            PropertyImage.objects.filter(property=property_listing).count(), 2
        )
        detail = self.client.get(
            reverse("property_detail", args=[property_listing.pk])
        )
        self.assertContains(detail, "room.png")
        self.assertContains(detail, "balcony.png")
        self.assertContains(detail, 'id="photo-lightbox"')
        self.assertContains(detail, "data-lightbox-next")

    def test_listing_rejects_more_than_eight_additional_photos(self):
        self.client.force_login(self.landlord)
        response = self.client.post(
            reverse("property_create"),
            {
                "title": "Too many photos",
                "description": "A rental with an oversized gallery.",
                "property_type": Property.PropertyType.APARTMENT,
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
                    self.image_upload(f"photo-{number}.png")
                    for number in range(9)
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload no more than 8 additional photos.")
        self.assertFalse(Property.objects.filter(title="Too many photos").exists())

    def test_service_provider_can_remove_own_gallery_photo(self):
        photo = PropertyImage.objects.create(
            property=self.listing,
            image=self.image_upload("living-room.png"),
        )
        self.client.force_login(self.landlord)

        response = self.client.post(
            reverse(
                "property_image_delete",
                args=[self.listing.pk, photo.pk],
            )
        )

        self.assertRedirects(
            response, reverse("property_edit", args=[self.listing.pk])
        )
        self.assertFalse(PropertyImage.objects.filter(pk=photo.pk).exists())

    def test_home_seeker_cannot_remove_provider_gallery_photo(self):
        photo = PropertyImage.objects.create(
            property=self.listing,
            image=self.image_upload("living-room.png"),
        )
        self.client.force_login(self.renter)

        response = self.client.post(
            reverse(
                "property_image_delete",
                args=[self.listing.pk, photo.pk],
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PropertyImage.objects.filter(pk=photo.pk).exists())

    def test_renter_can_save_and_remove_a_listing(self):
        self.client.force_login(self.renter)
        save_url = reverse("saved_property_toggle", args=[self.listing.pk])

        response = self.client.post(
            save_url,
            {"action": "save", "next": reverse("home")},
        )

        self.assertRedirects(response, reverse("home"))
        self.assertTrue(
            SavedProperty.objects.filter(
                renter=self.renter, property=self.listing
            ).exists()
        )
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "Garden apartment")
        self.assertContains(dashboard, "Saved places")

        response = self.client.post(
            save_url,
            {"action": "remove", "next": reverse("dashboard")},
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(
            SavedProperty.objects.filter(
                renter=self.renter, property=self.listing
            ).exists()
        )

    def test_saved_property_redirect_rejects_external_url(self):
        self.client.force_login(self.renter)

        response = self.client.post(
            reverse("saved_property_toggle", args=[self.listing.pk]),
            {"action": "save", "next": "https://example.com"},
        )

        self.assertRedirects(
            response, reverse("property_detail", args=[self.listing.pk])
        )

    def test_only_owner_can_publish_or_pause_a_property(self):
        self.client.force_login(self.other_landlord)
        response = self.client.post(
            reverse("property_status_update", args=[self.draft.pk]),
            {"status": Property.Status.PUBLISHED},
        )

        self.assertEqual(response.status_code, 404)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Property.Status.DRAFT)

        self.client.force_login(self.landlord)
        response = self.client.post(
            reverse("property_status_update", args=[self.draft.pk]),
            {"status": Property.Status.PUBLISHED},
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Property.Status.PUBLISHED)

    def test_landlord_dashboard_shows_listing_and_visit_summary(self):
        VisitRequest.objects.create(
            property=self.listing,
            renter=self.renter,
            scheduled_for=timezone.now() + timedelta(days=2),
        )
        self.client.force_login(self.landlord)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Requests to review")
        self.assertContains(response, "Garden apartment")
        self.assertContains(response, "1")

    def test_renter_can_request_future_visit(self):
        self.client.force_login(self.renter)
        scheduled_for = (timezone.localtime(timezone.now()) + timedelta(days=2)).replace(
            second=0, microsecond=0
        )
        response = self.client.post(
            reverse("visit_request_create", args=[self.listing.pk]),
            {"scheduled_for": scheduled_for.strftime("%Y-%m-%dT%H:%M"), "message": "After work"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(VisitRequest.objects.count(), 1)
        self.assertEqual(
            VisitRequest.objects.get().status, VisitRequest.Status.REQUESTED
        )

    def test_renter_cannot_create_duplicate_open_request(self):
        VisitRequest.objects.create(
            property=self.listing,
            renter=self.renter,
            scheduled_for=timezone.now() + timedelta(days=2),
        )
        self.client.force_login(self.renter)
        scheduled_for = (timezone.localtime(timezone.now()) + timedelta(days=3)).replace(
            second=0, microsecond=0
        )

        response = self.client.post(
            reverse("visit_request_create", args=[self.listing.pk]),
            {"scheduled_for": scheduled_for.strftime("%Y-%m-%dT%H:%M")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already have an open visit request")
        self.assertEqual(VisitRequest.objects.count(), 1)

    def test_visit_model_rejects_past_time_and_self_request(self):
        with self.assertRaises(ValidationError):
            VisitRequest.objects.create(
                property=self.listing,
                renter=self.renter,
                scheduled_for=timezone.now() - timedelta(minutes=1),
            )

        with self.assertRaises(ValidationError):
            VisitRequest.objects.create(
                property=self.listing,
                renter=self.landlord,
                scheduled_for=timezone.now() + timedelta(days=2),
            )

    def test_only_listing_owner_can_decide_visit_request(self):
        visit = VisitRequest.objects.create(
            property=self.listing,
            renter=self.renter,
            scheduled_for=timezone.now() + timedelta(days=2),
        )
        self.client.force_login(self.other_landlord)

        response = self.client.post(
            reverse("visit_request_decide", args=[visit.pk]),
            {"status": VisitRequest.Status.CONFIRMED},
        )

        self.assertEqual(response.status_code, 404)
        visit.refresh_from_db()
        self.assertEqual(visit.status, VisitRequest.Status.REQUESTED)

    def test_signup_creates_account_with_selected_role(self):
        signup_page = self.client.get(reverse("signup"))
        self.assertContains(signup_page, "Home seeker")
        self.assertContains(signup_page, "Service provider")
        self.assertContains(signup_page, "data-menu-toggle")
        self.assertContains(signup_page, "rentals/site.js")

        response = self.client.post(
            reverse("signup"),
            {
                "username": "new-landlord",
                "email": "NEW-LANDLORD@example.com",
                "first_name": "New",
                "last_name": "Owner",
                "role": User.Role.LANDLORD,
                "password1": "123",
                "password2": "123",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="new-landlord")
        self.assertEqual(user.email, "new-landlord@example.com")
        self.assertEqual(user.role, User.Role.LANDLORD)
