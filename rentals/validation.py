from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .models import Property, Reservation, User, VisitRequest


def _collection_schema(required, fields, enum_fields=None):
    properties = {
        name: {"bsonType": bson_type}
        for name, bson_type in fields.items()
    }
    for name, choices in (enum_fields or {}).items():
        properties[name]["enum"] = choices
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": required,
            "properties": properties,
        }
    }


MONGO_COLLECTION_VALIDATORS = {
    "rentals_user": _collection_schema(
        [
            "_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "password",
            "is_active",
            "date_joined",
        ],
        {
            "_id": "objectId",
            "username": "string",
            "email": "string",
            "first_name": "string",
            "last_name": "string",
            "role": "string",
            "password": "string",
            "is_active": "bool",
            "date_joined": "date",
        },
        {"role": User.Role.values},
    ),
    "rentals_property": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "_id",
                "owner_id",
                "title",
                "description",
                "property_type",
                "monthly_rent",
                "security_deposit",
                "address",
                "city",
                "state",
                "postal_code",
                "bedrooms",
                "bathrooms",
                "available_from",
                "status",
                "cover_image",
                "gallery",
                "created_at",
                "updated_at",
            ],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "owner_id": {"bsonType": "objectId"},
                "title": {"bsonType": "string"},
                "description": {"bsonType": "string"},
                "property_type": {
                    "enum": [choice for choice, _ in Property.PropertyType.choices]
                },
                "monthly_rent": {"bsonType": ["decimal", "double", "int", "long"]},
                "security_deposit": {"bsonType": ["decimal", "double", "int", "long"]},
                "address": {"bsonType": "string"},
                "city": {"bsonType": "string"},
                "state": {"bsonType": "string"},
                "postal_code": {"bsonType": "string"},
                "bedrooms": {"bsonType": ["int", "long"]},
                "bathrooms": {"bsonType": ["int", "long"]},
                "available_from": {"bsonType": "date"},
                "status": {
                    "enum": [choice for choice, _ in Property.Status.choices]
                },
                "cover_image": {"bsonType": "string"},
                "gallery": {
                    "bsonType": "array",
                    "maxItems": 8,
                    "items": {
                        "bsonType": "object",
                        "required": ["image_id", "image", "created_at"],
                        "properties": {
                            "image_id": {"bsonType": "string"},
                            "image": {"bsonType": "string"},
                            "created_at": {"bsonType": "date"},
                        },
                    },
                },
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
        }
    },
    "rentals_savedproperty": _collection_schema(
        ["_id", "renter_id", "property_id", "created_at"],
        {
            "_id": "objectId",
            "renter_id": "objectId",
            "property_id": "objectId",
            "created_at": "date",
        },
    ),
    "rentals_visitrequest": _collection_schema(
        [
            "_id",
            "property_id",
            "renter_id",
            "scheduled_for",
            "message",
            "status",
            "created_at",
            "updated_at",
        ],
        {
            "_id": "objectId",
            "property_id": "objectId",
            "renter_id": "objectId",
            "scheduled_for": "date",
            "message": "string",
            "status": "string",
            "created_at": "date",
            "updated_at": "date",
        },
        {"status": VisitRequest.Status.values},
    ),
    "rentals_reservation": _collection_schema(
        [
            "_id",
            "property_id",
            "renter_id",
            "start_date",
            "end_date",
            "message",
            "status",
            "created_at",
            "updated_at",
        ],
        {
            "_id": "objectId",
            "property_id": "objectId",
            "renter_id": "objectId",
            "start_date": "date",
            "end_date": "date",
            "message": "string",
            "status": "string",
            "created_at": "date",
            "updated_at": "date",
        },
        {"status": Reservation.Status.values},
    ),
    "django_session": _collection_schema(
        ["_id", "session_data", "expire_date"],
        {
            "_id": "string",
            "session_data": "string",
            "expire_date": "date",
        },
    ),
}


def _required_text(field, value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field.replace('_', ' ').capitalize()} is required.")
    return value.strip()


def validate_user_data(*, username, email, first_name, last_name, role, password):
    if role not in User.Role.values:
        raise ValueError("Choose a valid account role.")
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    return {
        "username": _required_text("username", username).lower(),
        "email": _required_text("email", email).lower(),
        "first_name": _required_text("first name", first_name),
        "last_name": _required_text("last name", last_name),
        "role": role,
        "password": password,
    }


def validate_password(password):
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")


def validate_property_data(values):
    validated = {
        field: _required_text(field, values.get(field))
        for field in (
            "title",
            "description",
            "address",
            "city",
            "state",
            "postal_code",
        )
    }
    cover_image = values.get("cover_image", "")
    if not isinstance(cover_image, str):
        raise ValueError("Cover image path must be text.")
    validated["cover_image"] = cover_image

    for field, choices in (
        ("property_type", Property.PropertyType.values),
        ("status", Property.Status.values),
    ):
        value = values.get(field)
        if value not in choices:
            raise ValueError(f"Choose a valid {field.replace('_', ' ')}.")
        validated[field] = value

    for field, minimum in (
        ("monthly_rent", Decimal("0.01")),
        ("security_deposit", Decimal("0")),
    ):
        try:
            amount = Decimal(str(values.get(field)))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValueError(f"{field.replace('_', ' ').capitalize()} must be a number.") from error
        if not amount.is_finite() or amount < minimum:
            raise ValueError(f"{field.replace('_', ' ').capitalize()} must be at least {minimum}.")
        validated[field] = amount

    for field in ("bedrooms", "bathrooms"):
        value = values.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{field.capitalize()} must be a positive whole number.")
        validated[field] = value

    available_from = values.get("available_from")
    if isinstance(available_from, datetime) or not isinstance(available_from, date):
        raise ValueError("Availability must be a valid date.")
    if available_from < timezone.localdate():
        raise ValueError("Availability cannot be in the past.")
    validated["available_from"] = available_from
    return validated


def validate_request_message(message):
    if not isinstance(message, str):
        raise ValueError("Message must be text.")
    return message.strip()


def validate_gallery_image(image_name):
    return _required_text("image path", image_name)


def validate_visit_data(scheduled_for, message):
    if not isinstance(scheduled_for, datetime):
        raise ValueError("Choose a valid visit time.")
    if timezone.is_naive(scheduled_for):
        scheduled_for = timezone.make_aware(scheduled_for)
    if scheduled_for <= timezone.now():
        raise ValueError("Choose a visit time in the future.")
    return scheduled_for, validate_request_message(message)


def validate_reservation_data(start_date, end_date, message):
    if (
        isinstance(start_date, datetime)
        or isinstance(end_date, datetime)
        or not isinstance(start_date, date)
        or not isinstance(end_date, date)
    ):
        raise ValueError("Choose valid check-in and check-out dates.")
    if start_date < timezone.localdate():
        raise ValueError("Check-in cannot be in the past.")
    if end_date <= start_date:
        raise ValueError("Check-out must be after check-in.")
    return start_date, end_date, validate_request_message(message)
