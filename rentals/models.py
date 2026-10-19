from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class UserRole(StrEnum):
    RENTER = "renter"
    LANDLORD = "landlord"

    @classmethod
    def choices(cls):
        return [(item.value, "Home seeker" if item is cls.RENTER else "Service provider") for item in cls]


class PropertyType(StrEnum):
    HOUSE = "house"
    PG = "pg"
    HOSTEL = "hostel"
    APARTMENT = "apartment"

    @classmethod
    def choices(cls):
        labels = {
            cls.HOUSE: "House",
            cls.PG: "Paying guest",
            cls.HOSTEL: "Hostel",
            cls.APARTMENT: "Apartment",
        }
        return [(item.value, labels[item]) for item in cls]


class PropertyStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    PAUSED = "paused"
    ARCHIVED = "archived"

    @classmethod
    def choices(cls):
        return [(item.value, item.value.title()) for item in cls]


class RequestStatus(StrEnum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass
class User:
    class Role:
        RENTER = UserRole.RENTER.value
        LANDLORD = UserRole.LANDLORD.value
        choices = UserRole.choices

    id: str
    username: str
    email: str
    first_name: str
    last_name: str
    role: str
    is_authenticated: bool = True
    is_staff: bool = False

    @property
    def pk(self):
        return self.id

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_role_display(self):
        return "Home seeker" if self.role == UserRole.RENTER else "Service provider"


@dataclass
class StoredImage:
    name: str = ""

    @property
    def url(self):
        from django.conf import settings

        return f"{settings.MEDIA_URL}{self.name}" if self.name else ""

    def __bool__(self):
        return bool(self.name)


@dataclass
class Property:
    PropertyType = PropertyType
    Status = PropertyStatus

    id: str
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
    cover_image: StoredImage = field(default_factory=StoredImage)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    gallery_images: list[Any] = field(default_factory=list)
    visit_count: int = 0

    @property
    def pk(self):
        return self.id

    @property
    def owner_id(self):
        return self.owner.id

    def get_status_display(self):
        return self.status.title()

    def get_property_type_display(self):
        return {
            PropertyType.HOUSE: "House",
            PropertyType.PG: "Paying guest",
            PropertyType.HOSTEL: "Hostel",
            PropertyType.APARTMENT: "Apartment",
        }.get(self.property_type, self.property_type.title())


@dataclass
class PropertyImage:
    id: str
    property_id: str
    image: StoredImage
    created_at: datetime

    @property
    def pk(self):
        return self.id


@dataclass
class VisitRequest:
    class Status:
        REQUESTED = RequestStatus.REQUESTED.value
        CONFIRMED = RequestStatus.CONFIRMED.value
        DECLINED = RequestStatus.DECLINED.value
        CANCELLED = RequestStatus.CANCELLED.value
        COMPLETED = RequestStatus.COMPLETED.value

    id: str
    property: Property
    renter: User
    scheduled_for: datetime
    message: str
    status: str
    created_at: datetime
    updated_at: datetime

    @property
    def pk(self):
        return self.id

    def get_status_display(self):
        return self.status.title()


@dataclass
class Reservation:
    class Status:
        REQUESTED = RequestStatus.REQUESTED.value
        CONFIRMED = RequestStatus.CONFIRMED.value
        DECLINED = RequestStatus.DECLINED.value
        CANCELLED = RequestStatus.CANCELLED.value
        COMPLETED = RequestStatus.COMPLETED.value

    id: str
    property: Property
    renter: User
    start_date: date
    end_date: date
    message: str
    status: str
    created_at: datetime
    updated_at: datetime

    @property
    def pk(self):
        return self.id

    def get_status_display(self):
        return self.status.title()
