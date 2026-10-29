from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class User:
    class Role(models.TextChoices):
        RENTER = "renter", "Home seeker"
        LANDLORD = "landlord", "Service provider"

    def __init__(
        self,
        *,
        id,
        username,
        email,
        first_name="",
        last_name="",
        role=Role.RENTER,
        password="",
        is_active=True,
        is_staff=False,
        is_superuser=False,
    ):
        self.id = id
        self.pk = id
        self.username = username
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.role = role
        self.password = password
        self.is_active = is_active
        self.is_staff = is_staff
        self.is_superuser = is_superuser

    @property
    def is_authenticated(self):
        return True

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_role_display(self):
        return self.Role(self.role).label

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)


class AnonymousUser:
    id = None
    pk = None
    role = None
    is_staff = False
    is_superuser = False
    is_active = False
    is_authenticated = False
    username = ""
    email = ""
    first_name = ""
    last_name = ""

    def get_full_name(self):
        return ""

    def get_role_display(self):
        return ""


@dataclass
class StoredFile:
    name: str = ""

    def __bool__(self):
        return bool(self.name)

    @property
    def url(self):
        return f"{settings.MEDIA_URL}{self.name}" if self.name else ""


@dataclass
class PropertyImage:
    image_id: str
    image: StoredFile
    created_at: datetime


@dataclass
class Property:
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

    id: object
    owner_id: object
    owner: User
    title: str
    description: str
    property_type: str
    monthly_rent: Decimal
    security_deposit: Decimal
    address: str
    city: str
    state: str
    postal_code: str
    bedrooms: int
    bathrooms: int
    available_from: date
    status: str
    cover_image: StoredFile = field(default_factory=StoredFile)
    gallery: list = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def pk(self):
        return self.id

    @property
    def gallery_images(self):
        return self.gallery

    def get_property_type_display(self):
        return self.PropertyType(self.property_type).label

    def get_status_display(self):
        return self.Status(self.status).label


class VisitRequest:
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    def __init__(
        self, *, id, property, renter, scheduled_for, message="", status=Status.REQUESTED,
        created_at=None, updated_at=None,
    ):
        self.id = id
        self.pk = id
        self.property = property
        self.renter = renter
        self.scheduled_for = scheduled_for
        self.message = message
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at

    def get_status_display(self):
        return self.Status(self.status).label


class Reservation:
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    def __init__(
        self, *, id, property, renter, start_date, end_date, message="",
        status=Status.REQUESTED, created_at=None, updated_at=None,
    ):
        self.id = id
        self.pk = id
        self.property = property
        self.renter = renter
        self.start_date = start_date
        self.end_date = end_date
        self.message = message
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at

    def get_status_display(self):
        return self.Status(self.status).label
