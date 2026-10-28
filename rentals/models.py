import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


def new_model_id():
    return uuid.uuid4().hex


def property_cover_path(instance, filename):
    return f"properties/{instance.owner_id}/covers/{filename}"


def property_gallery_path(instance, filename):
    return f"properties/{instance.property.owner_id}/gallery/{filename}"


class User(AbstractUser):
    class Role(models.TextChoices):
        RENTER = "renter", "Home seeker"
        LANDLORD = "landlord", "Service provider"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.RENTER)
    email = models.EmailField(unique=True)

    def save(self, *args, **kwargs):
        self.username = self.username.strip().lower()
        self.email = self.email.strip().lower()
        return super().save(*args, **kwargs)


class Property(models.Model):
    class PropertyType(models.TextChoices):
        HOUSE = "house", "House"
        PG = "pg", "Paying guest"
        HOSTEL = "hostel", "Hostel"
        APARTMENT = "apartment", "Apartment"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        PAUSED = "paused", "Paused"
        ARCHIVED = "archived", "Archived"

    id = models.CharField(primary_key=True, max_length=32, default=new_model_id, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="properties",
    )
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=4000)
    property_type = models.CharField(max_length=20, choices=PropertyType.choices)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    address = models.CharField(max_length=250)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=12)
    bedrooms = models.PositiveSmallIntegerField()
    bathrooms = models.PositiveSmallIntegerField()
    available_from = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    cover_image = models.ImageField(
        upload_to=property_cover_path,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "city")),
            models.Index(fields=("owner", "-created_at")),
        ]

    def __str__(self):
        return self.title

    @property
    def gallery_images(self):
        return list(self.gallery.all())


class PropertyImage(models.Model):
    id = models.CharField(primary_key=True, max_length=32, default=new_model_id, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="gallery",
    )
    image = models.ImageField(upload_to=property_gallery_path)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class SavedProperty(models.Model):
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_properties",
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="saved_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("renter", "property"),
                name="unique_saved_property_per_renter",
            )
        ]


class VisitRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    id = models.CharField(primary_key=True, max_length=32, default=new_model_id, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="visit_requests",
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="visit_requests",
    )
    scheduled_for = models.DateTimeField()
    message = models.CharField(max_length=1000, blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("scheduled_for",)
        constraints = [
            models.UniqueConstraint(
                fields=("property", "renter"),
                condition=Q(status__in=("requested", "confirmed")),
                name="one_open_visit_per_renter_property",
            )
        ]

    def get_status_display(self):
        return self.Status(self.status).label


class Reservation(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    id = models.CharField(primary_key=True, max_length=32, default=new_model_id, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    message = models.CharField(max_length=1000, blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("start_date", "created_at")
        indexes = [models.Index(fields=("property", "start_date"))]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gt=models.F("start_date")),
                name="reservation_end_after_start",
            )
        ]

    def get_status_display(self):
        return self.Status(self.status).label
