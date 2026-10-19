import re
from datetime import date, timezone
from decimal import Decimal
from functools import lru_cache
from threading import Lock

from bson import Decimal128, ObjectId
from bson.errors import InvalidId
from django.conf import settings
from django.utils import timezone as django_timezone
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError

from .models import (
    Property,
    PropertyImage,
    PropertyStatus,
    Reservation,
    RequestStatus,
    StoredImage,
    User,
    VisitRequest,
)

_indexed_databases = set()
_index_lock = Lock()


@lru_cache(maxsize=4)
def _client(uri):
    return MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True, tzinfo=timezone.utc)


def _raw_database():
    return _client(settings.MONGODB_URI)[settings.MONGODB_DATABASE]


def _create_indexes(db):
    db.users.create_index("username_lower", unique=True)
    db.users.create_index("email", unique=True)
    db.properties.create_index([("status", ASCENDING), ("city_lower", ASCENDING)])
    db.properties.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
    db.property_images.create_index([("property_id", ASCENDING), ("created_at", ASCENDING)])
    db.saved_properties.create_index(
        [("renter_id", ASCENDING), ("property_id", ASCENDING)], unique=True
    )
    db.visit_requests.create_index(
        [("property_id", ASCENDING), ("renter_id", ASCENDING)],
        unique=True,
        partialFilterExpression={"status": {"$in": [RequestStatus.REQUESTED, RequestStatus.CONFIRMED]}},
    )
    db.visit_requests.create_index([("property_id", ASCENDING), ("scheduled_for", ASCENDING)])
    db.reservations.create_index([("property_id", ASCENDING), ("start_date", ASCENDING)])


def database():
    db = _raw_database()
    key = (settings.MONGODB_URI, settings.MONGODB_DATABASE)
    if key not in _indexed_databases:
        with _index_lock:
            if key not in _indexed_databases:
                _create_indexes(db)
                _indexed_databases.add(key)
    return db


def ensure_indexes(*, force=False):
    db = _raw_database()
    key = (settings.MONGODB_URI, settings.MONGODB_DATABASE)
    if force or key not in _indexed_databases:
        with _index_lock:
            if force or key not in _indexed_databases:
                _create_indexes(db)
                _indexed_databases.add(key)


def _id(value):
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None


def _user_from_doc(doc):
    if not doc or not doc.get("is_active", True):
        return None
    return User(
        id=str(doc["_id"]),
        username=doc["username"],
        email=doc["email"],
        first_name=doc.get("first_name", ""),
        last_name=doc.get("last_name", ""),
        role=doc["role"],
        is_staff=bool(doc.get("is_staff", False)),
    )


def get_user(user_id):
    object_id = _id(user_id)
    return _user_from_doc(database().users.find_one({"_id": object_id})) if object_id else None


def find_user_by_username(username):
    return database().users.find_one({"username_lower": username.strip().lower()})


def find_user_by_email(email):
    return database().users.find_one({"email": email.strip().lower()})


def create_user(*, username, email, first_name, last_name, role, password_hash):
    ensure_indexes()
    username = username.strip()
    email = email.strip().lower()
    now = django_timezone.now()
    doc = {
        "username": username,
        "username_lower": username.lower(),
        "email": email,
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "role": role,
        "password_hash": password_hash,
        "is_active": True,
        "is_staff": False,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = database().users.insert_one(doc)
    except DuplicateKeyError as error:
        if database().users.find_one({"email": email}):
            raise ValueError("An account with this email already exists.") from error
        raise ValueError("That username is already taken.") from error
    doc["_id"] = result.inserted_id
    return _user_from_doc(doc)


def _property_from_doc(doc, *, with_gallery=False):
    if not doc:
        return None
    owner = get_user(doc["owner_id"])
    if owner is None:
        raise RuntimeError(f"Property {doc['_id']} refers to a missing owner.")
    prop = Property(
        id=str(doc["_id"]),
        owner=owner,
        title=doc["title"],
        description=doc["description"],
        property_type=doc["property_type"],
        monthly_rent=Decimal(str(doc["monthly_rent"].to_decimal())),
        security_deposit=Decimal(str(doc["security_deposit"].to_decimal())),
        address=doc["address"],
        city=doc["city"],
        state=doc["state"],
        postal_code=doc["postal_code"],
        bedrooms=doc["bedrooms"],
        bathrooms=doc["bathrooms"],
        available_from=date.fromisoformat(doc["available_from"]),
        status=doc["status"],
        cover_image=StoredImage(doc.get("cover_image", "")),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )
    if with_gallery:
        prop.gallery_images = list_property_images(prop.id)
    return prop


def get_property(property_id, *, owner_id=None, status=None, with_gallery=False):
    object_id = _id(property_id)
    if object_id is None:
        return None
    query = {"_id": object_id}
    if owner_id is not None:
        owner_object_id = _id(owner_id)
        if owner_object_id is None:
            return None
        query["owner_id"] = owner_object_id
    if status is not None:
        query["status"] = status
    return _property_from_doc(database().properties.find_one(query), with_gallery=with_gallery)


def _property_document(values, owner_id, *, existing=None):
    now = django_timezone.now()
    return {
        "owner_id": _id(owner_id),
        "title": values["title"],
        "description": values["description"],
        "property_type": values["property_type"],
        "monthly_rent": Decimal128(str(values["monthly_rent"])),
        "security_deposit": Decimal128(str(values["security_deposit"])),
        "address": values["address"],
        "city": values["city"],
        "city_lower": values["city"].strip().lower(),
        "state": values["state"],
        "postal_code": values["postal_code"],
        "bedrooms": values["bedrooms"],
        "bathrooms": values["bathrooms"],
        "available_from": values["available_from"].isoformat(),
        "status": values["status"],
        "cover_image": values.get("cover_image", existing.get("cover_image", "") if existing else ""),
        "created_at": existing["created_at"] if existing else now,
        "updated_at": now,
    }


def create_property(values, owner_id):
    doc = _property_document(values, owner_id)
    result = database().properties.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _property_from_doc(doc)


def update_property(property_id, values, owner_id):
    object_id = _id(property_id)
    existing = database().properties.find_one({"_id": object_id, "owner_id": _id(owner_id)})
    if existing is None:
        return None
    doc = _property_document(values, owner_id, existing=existing)
    database().properties.update_one({"_id": object_id}, {"$set": doc})
    return _property_from_doc({**doc, "_id": object_id})


def update_property_status(property_id, owner_id, status):
    result = database().properties.update_one(
        {"_id": _id(property_id), "owner_id": _id(owner_id)},
        {"$set": {"status": status, "updated_at": django_timezone.now()}},
    )
    return result.matched_count == 1


def list_properties(*, owner_id=None, status=None, filters=None, sort="newest"):
    query = {}
    if owner_id is not None:
        query["owner_id"] = _id(owner_id)
    if status is not None:
        query["status"] = status
    filters = filters or {}
    city = filters.get("city")
    if city:
        query["city_lower"] = {"$regex": re.escape(city.strip().lower())}
    if filters.get("property_type"):
        query["property_type"] = filters["property_type"]
    rent = {}
    if filters.get("min_rent") is not None:
        rent["$gte"] = Decimal128(str(filters["min_rent"]))
    if filters.get("max_rent") is not None:
        rent["$lte"] = Decimal128(str(filters["max_rent"]))
    if rent:
        query["monthly_rent"] = rent
    if filters.get("min_bedrooms"):
        query["bedrooms"] = {"$gte": filters["min_bedrooms"]}
    if filters.get("move_in_date"):
        query["available_from"] = {"$lte": filters["move_in_date"].isoformat()}
    sort_field, direction = {
        "rent_low": ("monthly_rent", ASCENDING),
        "rent_high": ("monthly_rent", DESCENDING),
        "available": ("available_from", ASCENDING),
    }.get(sort, ("created_at", DESCENDING))
    cursor = database().properties.find(query).sort(
        [(sort_field, direction), ("created_at", DESCENDING)]
    )
    return [_property_from_doc(doc) for doc in cursor]


def count_visits_for_property(property_id):
    return database().visit_requests.count_documents({"property_id": _id(property_id)})


def _property_image_from_doc(doc):
    return PropertyImage(
        id=str(doc["_id"]),
        property_id=str(doc["property_id"]),
        image=StoredImage(doc["image"]),
        created_at=doc["created_at"],
    )


def create_property_image(property_id, image_name):
    now = django_timezone.now()
    doc = {"property_id": _id(property_id), "image": image_name, "created_at": now}
    result = database().property_images.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _property_image_from_doc(doc)


def list_property_images(property_id):
    return [
        _property_image_from_doc(doc)
        for doc in database().property_images.find({"property_id": _id(property_id)}).sort("created_at", ASCENDING)
    ]


def delete_property_image(property_id, image_id):
    return database().property_images.find_one_and_delete(
        {"_id": _id(image_id), "property_id": _id(property_id)}
    )


def get_image_count(property_id):
    return database().property_images.count_documents({"property_id": _id(property_id)})


def saved_property_ids(renter_id):
    return {
        str(doc["property_id"])
        for doc in database().saved_properties.find({"renter_id": _id(renter_id)}, {"property_id": 1})
    }


def list_saved_properties(renter_id):
    saved_ids = [doc["property_id"] for doc in database().saved_properties.find({"renter_id": _id(renter_id)})]
    if not saved_ids:
        return []
    return [
        _property_from_doc(doc)
        for doc in database().properties.find(
            {"_id": {"$in": saved_ids}, "status": PropertyStatus.PUBLISHED}
        ).sort("created_at", DESCENDING)
    ]


def set_saved_property(renter_id, property_id, save):
    ensure_indexes()
    key = {"renter_id": _id(renter_id), "property_id": _id(property_id)}
    if save:
        database().saved_properties.update_one(
            key,
            {"$setOnInsert": {**key, "created_at": django_timezone.now()}},
            upsert=True,
        )
    else:
        database().saved_properties.delete_one(key)


def _visit_from_doc(doc):
    return VisitRequest(
        id=str(doc["_id"]),
        property=get_property(doc["property_id"]),
        renter=get_user(doc["renter_id"]),
        scheduled_for=doc["scheduled_for"],
        message=doc.get("message", ""),
        status=doc["status"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def create_visit(property_id, renter_id, scheduled_for, message=""):
    prop = get_property(property_id)
    renter = get_user(renter_id)
    if prop is None or renter is None:
        raise ValueError("The selected listing or account no longer exists.")
    if prop.owner_id == renter.id:
        raise ValueError("You cannot request a visit to your own property.")
    if scheduled_for <= django_timezone.now():
        raise ValueError("Choose a visit time in the future.")
    ensure_indexes()
    now = django_timezone.now()
    doc = {
        "property_id": _id(property_id),
        "renter_id": _id(renter_id),
        "scheduled_for": scheduled_for,
        "message": message,
        "status": RequestStatus.REQUESTED,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = database().visit_requests.insert_one(doc)
    except DuplicateKeyError as error:
        raise ValueError("You already have an open visit request for this property. Cancel or finish it before requesting another.") from error
    doc["_id"] = result.inserted_id
    return _visit_from_doc(doc)


def _owned_property_ids(owner_id):
    return [doc["_id"] for doc in database().properties.find({"owner_id": _id(owner_id)}, {"_id": 1})]


def list_visits(*, renter_id=None, owner_id=None):
    query = {}
    if renter_id is not None:
        query["renter_id"] = _id(renter_id)
    elif owner_id is not None:
        query["property_id"] = {"$in": _owned_property_ids(owner_id)}
    return [_visit_from_doc(doc) for doc in database().visit_requests.find(query).sort("scheduled_for", ASCENDING)]


def get_visit(visit_id, *, renter_id=None, owner_id=None, status=None):
    query = {"_id": _id(visit_id)}
    if renter_id is not None:
        query["renter_id"] = _id(renter_id)
    if owner_id is not None:
        query["property_id"] = {"$in": _owned_property_ids(owner_id)}
    if status is not None:
        query["status"] = status
    return _visit_from_doc(database().visit_requests.find_one(query)) if query["_id"] else None


def update_visit_status(visit_id, status):
    return database().visit_requests.update_one(
        {"_id": _id(visit_id)}, {"$set": {"status": status, "updated_at": django_timezone.now()}}
    ).matched_count == 1


def _reservation_from_doc(doc):
    return Reservation(
        id=str(doc["_id"]),
        property=get_property(doc["property_id"]),
        renter=get_user(doc["renter_id"]),
        start_date=date.fromisoformat(doc["start_date"]),
        end_date=date.fromisoformat(doc["end_date"]),
        message=doc.get("message", ""),
        status=doc["status"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def create_reservation(property_id, renter_id, start_date, end_date, message=""):
    prop = get_property(property_id)
    if prop is None or get_user(renter_id) is None:
        raise ValueError("The selected listing or account no longer exists.")
    if prop.owner_id == str(renter_id):
        raise ValueError("You cannot book your own property.")
    today = django_timezone.localdate()
    if start_date < today:
        raise ValueError("Check-in cannot be in the past.")
    if end_date <= start_date:
        raise ValueError("Check-out must be after check-in.")
    query = {
        "property_id": _id(property_id),
        "status": {"$in": [RequestStatus.REQUESTED, RequestStatus.CONFIRMED]},
        "start_date": {"$lt": end_date.isoformat()},
        "end_date": {"$gt": start_date.isoformat()},
    }
    if database().reservations.find_one(query):
        raise ValueError("These dates overlap another active booking request for this property.")
    now = django_timezone.now()
    doc = {
        "property_id": _id(property_id),
        "renter_id": _id(renter_id),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "message": message,
        "status": RequestStatus.REQUESTED,
        "created_at": now,
        "updated_at": now,
    }
    result = database().reservations.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _reservation_from_doc(doc)


def list_reservations(*, renter_id=None, owner_id=None):
    query = {}
    if renter_id is not None:
        query["renter_id"] = _id(renter_id)
    elif owner_id is not None:
        query["property_id"] = {"$in": _owned_property_ids(owner_id)}
    return [
        _reservation_from_doc(doc)
        for doc in database().reservations.find(query).sort(
            [("start_date", ASCENDING), ("created_at", ASCENDING)]
        )
    ]


def get_reservation(reservation_id, *, renter_id=None, owner_id=None, status=None):
    query = {"_id": _id(reservation_id)}
    if renter_id is not None:
        query["renter_id"] = _id(renter_id)
    if owner_id is not None:
        query["property_id"] = {"$in": _owned_property_ids(owner_id)}
    if status is not None:
        query["status"] = status
    doc = database().reservations.find_one(query) if query["_id"] else None
    return _reservation_from_doc(doc) if doc else None


def update_reservation_status(reservation_id, status):
    object_id = _id(reservation_id)
    if status == RequestStatus.CONFIRMED:
        current = database().reservations.find_one({"_id": object_id})
        if current is None:
            return False
        conflict = database().reservations.find_one(
            {
                "_id": {"$ne": object_id},
                "property_id": current["property_id"],
                "status": {"$in": [RequestStatus.REQUESTED, RequestStatus.CONFIRMED]},
                "start_date": {"$lt": current["end_date"]},
                "end_date": {"$gt": current["start_date"]},
            }
        )
        if conflict:
            raise ValueError("These dates overlap another active booking request for this property.")
    return database().reservations.update_one(
        {"_id": object_id}, {"$set": {"status": status, "updated_at": django_timezone.now()}}
    ).matched_count == 1
