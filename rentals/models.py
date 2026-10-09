from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        RENTER = "renter", "Home seeker"
        LANDLORD = "landlord", "Service provider"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.RENTER)

    def __str__(self):
        return self.get_full_name() or self.username


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

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="properties",
    )
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=4000)
    property_type = models.CharField(max_length=12, choices=PropertyType.choices)
    monthly_rent = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    security_deposit = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    address = models.CharField(max_length=250)
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=12)
    bedrooms = models.PositiveSmallIntegerField(default=1)
    bathrooms = models.PositiveSmallIntegerField(default=1)
    available_from = models.DateField(default=timezone.localdate, db_index=True)
    cover_image = models.ImageField(upload_to="properties/%Y/%m/", blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "city", "property_type"]),
            models.Index(fields=["status", "monthly_rent"]),
        ]

    def __str__(self):
        return self.title


class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = models.ImageField(upload_to="properties/gallery/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Photo for {self.property}"


class VisitRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    property = models.ForeignKey(
        Property, on_delete=models.PROTECT, related_name="visit_requests"
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="visit_requests",
    )
    scheduled_for = models.DateTimeField()
    message = models.CharField(max_length=1000, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.REQUESTED, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_for"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "renter"],
                condition=Q(status__in=["requested", "confirmed"]),
                name="one_open_visit_per_renter_property",
            )
        ]

    def clean(self):
        super().clean()
        scheduled_for_changed = self._state.adding
        if self.pk and not self._state.adding:
            previous_time = (
                type(self).objects.filter(pk=self.pk)
                .values_list("scheduled_for", flat=True)
                .first()
            )
            scheduled_for_changed = previous_time != self.scheduled_for
        if (
            scheduled_for_changed
            and self.scheduled_for
            and self.scheduled_for <= timezone.now()
        ):
            raise ValidationError(
                {"scheduled_for": "Choose a visit time in the future."}
            )
        if self.property_id and self.renter_id:
            if self.property.owner_id == self.renter_id:
                raise ValidationError(
                    {"renter": "You cannot request a visit to your own property."}
                )

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Visit for {self.property} by {self.renter}"


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
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["renter", "property"],
                name="one_saved_property_per_renter",
            )
        ]

    def __str__(self):
        return f"{self.renter} saved {self.property}"


class Reservation(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    property = models.ForeignKey(
        Property, on_delete=models.PROTECT, related_name="reservations"
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    message = models.CharField(max_length=1000, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.REQUESTED, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "created_at"]

    def clean(self):
        super().clean()
        errors = {}
        today = timezone.localdate()

        if (
            self.status in {self.Status.REQUESTED, self.Status.CONFIRMED}
            and self.start_date
            and self.start_date < today
        ):
            errors["start_date"] = "Check-in date cannot be in the past."
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            errors["end_date"] = "Check-out must be after check-in."
        if self.property_id and self.renter_id:
            if self.property.owner_id == self.renter_id:
                errors["renter"] = "You cannot book your own listing."
            if self.status in {self.Status.REQUESTED, self.Status.CONFIRMED}:
                if self.start_date and self.start_date < self.property.available_from:
                    errors["start_date"] = "This place is not available by that date."
                if self.property.status != Property.Status.PUBLISHED:
                    errors["property"] = "This listing is not currently available."
                if self.start_date and self.end_date and self.end_date > self.start_date:
                    conflicts = type(self).objects.filter(
                        property_id=self.property_id,
                        status__in=[self.Status.REQUESTED, self.Status.CONFIRMED],
                        start_date__lt=self.end_date,
                        end_date__gt=self.start_date,
                    )
                    if self.pk:
                        conflicts = conflicts.exclude(pk=self.pk)
                    if conflicts.exists():
                        errors["start_date"] = (
                            "These dates overlap another active booking request."
                        )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Reservation for {self.property} by {self.renter}"
