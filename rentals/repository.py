import re
from datetime import date, datetime, time, timezone as datetime_timezone
from decimal import Decimal

from bson import Decimal128, ObjectId
from pymongo.errors import DuplicateKeyError

from .database import get_database
from .models import (
    Property,
    PropertyImage,
    Reservation,
    StoredFile,
    User,
    VisitRequest,
)
from .validation import (
    validate_gallery_image,
    validate_password,
    validate_property_data,
    validate_reservation_data,
    validate_user_data,
    validate_visit_data,
)


def _db_id(value):
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return value


def _parse_id(value):
    if value in (None, ""):
        return None
    return _db_id(value)


def _stored_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    return value


def _mongo_date(value):
    if isinstance(value, datetime):
        return value.astimezone(datetime_timezone.utc) if value.tzinfo else value.replace(tzinfo=datetime_timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=datetime_timezone.utc)
    return value


def _stored_decimal(value):
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _mongo_value(value):
    if isinstance(value, Decimal):
        return Decimal128(value)
    if isinstance(value, date):
        return _mongo_date(value)
    return value


def _user_from_document(document):
    if document is None:
        return None
    return User(
        id=document["_id"],
        username=document.get("username", ""),
        email=document.get("email", ""),
        first_name=document.get("first_name", ""),
        last_name=document.get("last_name", ""),
        role=document.get("role", User.Role.RENTER),
        password=document.get("password", document.get("password_hash", "")),
        is_active=document.get("is_active", True),
        is_staff=document.get("is_staff", False),
        is_superuser=document.get("is_superuser", False),
    )


def _property_from_document(document):
    if document is None:
        return None
    owner_id = _db_id(document.get("owner_id"))
    owner = get_user(owner_id)
    if owner is None:
        return None
    gallery = [
        PropertyImage(
            image_id=str(item.get("image_id", item.get("_id", ObjectId()))),
            image=StoredFile(str(item.get("image", ""))),
            created_at=item.get("created_at"),
        )
        for item in document.get("gallery", [])
    ]
    return Property(
        id=document["_id"],
        owner_id=owner_id,
        owner=owner,
        title=document.get("title", ""),
        description=document.get("description", ""),
        property_type=document.get("property_type", Property.PropertyType.HOUSE),
        monthly_rent=_stored_decimal(document.get("monthly_rent", 0)),
        security_deposit=_stored_decimal(document.get("security_deposit", 0)),
        address=document.get("address", ""),
        city=document.get("city", ""),
        state=document.get("state", ""),
        postal_code=document.get("postal_code", ""),
        bedrooms=document.get("bedrooms", 0),
        bathrooms=document.get("bathrooms", 0),
        available_from=_stored_date(document.get("available_from")),
        status=document.get("status", Property.Status.DRAFT),
        cover_image=StoredFile(str(document.get("cover_image", ""))),
        gallery=gallery,
        created_at=document.get("created_at"),
        updated_at=document.get("updated_at"),
    )


def _request_from_document(document, model):
    if document is None:
        return None
    listing = get_property(document.get("property_id"))
    renter = get_user(document.get("renter_id"))
    if listing is None or renter is None:
        return None
    values = {
        "id": document["_id"],
        "property": listing,
        "renter": renter,
        "message": document.get("message", ""),
        "status": document.get("status", model.Status.REQUESTED),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }
    if model is VisitRequest:
        values["scheduled_for"] = document["scheduled_for"]
    else:
        values["start_date"] = _stored_date(document["start_date"])
        values["end_date"] = _stored_date(document["end_date"])
    return model(**values)


def _request_owner_filter(owner_id):
    property_ids = [
        document["_id"]
        for document in get_database()["rentals_property"].find(
            {"owner_id": _db_id(owner_id)},
            {"_id": 1},
        )
    ]
    return {"property_id": {"$in": property_ids}}


def get_user(user_id):
    parsed_id = _parse_id(user_id)
    if parsed_id is None:
        return None
    return _user_from_document(
        get_database()["rentals_user"].find_one(
            {"_id": parsed_id, "is_active": True}
        )
    )


def find_user_by_username(username):
    return _user_from_document(
        get_database()["rentals_user"].find_one(
            {"username": username.strip().lower()}
        )
    )


def find_user_by_email(email):
    return _user_from_document(
        get_database()["rentals_user"].find_one(
            {"email": email.strip().lower()}
        )
    )


def authenticate_user(username, password):
    user = find_user_by_username(username)
    return user if user and user.check_password(password) else None


def create_user(*, username, email, first_name, last_name, role, password):
    user_data = validate_user_data(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        password=password,
    )
    user = User(
        id=ObjectId(),
        username=user_data["username"],
        email=user_data["email"],
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        role=user_data["role"],
    )
    user.set_password(user_data["password"])
    document = {
        "_id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "password": user.password,
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
        "date_joined": datetime.now(datetime_timezone.utc),
    }
    try:
        get_database()["rentals_user"].insert_one(document)
    except DuplicateKeyError as error:
        if find_user_by_email(email):
            raise ValueError("An account with this email already exists.") from error
        if find_user_by_username(username):
            raise ValueError("That username is already taken.") from error
        raise
    return user


def set_user_password(user_id, raw_password):
    validate_password(raw_password)
    user = get_user(user_id)
    if user is None:
        return False
    user.set_password(raw_password)
    result = get_database()["rentals_user"].update_one(
        {"_id": user.id},
        {"$set": {"password": user.password}},
    )
    return result.modified_count == 1


def get_property(property_id, *, owner_id=None, status=None):
    parsed_id = _parse_id(property_id)
    if parsed_id is None:
        return None
    query = {"_id": parsed_id}
    if owner_id is not None:
        query["owner_id"] = _db_id(owner_id)
    if status is not None:
        query["status"] = status
    return _property_from_document(
        get_database()["rentals_property"].find_one(query)
    )


def create_property(values, owner_id):
    values = validate_property_data(values)
    owner = get_user(owner_id)
    if owner is None or owner.role != User.Role.LANDLORD:
        raise ValueError("Only an active service provider can create a listing.")
    document = {
        "_id": ObjectId(),
        "owner_id": _db_id(owner_id),
        "gallery": [],
        "created_at": datetime.now(datetime_timezone.utc),
        "updated_at": datetime.now(datetime_timezone.utc),
    }
    document.update({key: _mongo_value(value) for key, value in values.items()})
    get_database()["rentals_property"].insert_one(document)
    return _property_from_document(document)


def update_property(property_id, values, owner_id):
    values = validate_property_data(values)
    parsed_id = _parse_id(property_id)
    if parsed_id is None:
        return None
    updates = {key: _mongo_value(value) for key, value in values.items()}
    updates["updated_at"] = datetime.now(datetime_timezone.utc)
    result = get_database()["rentals_property"].update_one(
        {"_id": parsed_id, "owner_id": _db_id(owner_id)},
        {"$set": updates},
    )
    if result.matched_count != 1:
        return None
    return get_property(parsed_id)


def update_property_status(property_id, owner_id, status):
    if status not in Property.Status.values:
        raise ValueError("Choose a valid listing status.")
    result = get_database()["rentals_property"].update_one(
        {"_id": _parse_id(property_id), "owner_id": _db_id(owner_id)},
        {
            "$set": {
                "status": status,
                "updated_at": datetime.now(datetime_timezone.utc),
            }
        },
    )
    return result.modified_count == 1


def list_properties(*, owner_id=None, status=None, filters=None, sort="newest"):
    query = {}
    if owner_id is not None:
        query["owner_id"] = _db_id(owner_id)
    if status is not None:
        query["status"] = status
    filters = filters or {}
    keyword = filters.get("q")
    if keyword:
        expression = re.escape(keyword.strip())
        query["$or"] = [
            {field: {"$regex": expression, "$options": "i"}}
            for field in ("title", "description", "address", "city")
        ]
    if filters.get("city"):
        query["city"] = {"$regex": re.escape(filters["city"].strip()), "$options": "i"}
    if filters.get("property_type"):
        query["property_type"] = filters["property_type"]
    rent_filter = {}
    if filters.get("min_rent") is not None:
        rent_filter["$gte"] = _mongo_value(filters["min_rent"])
    if filters.get("max_rent") is not None:
        rent_filter["$lte"] = _mongo_value(filters["max_rent"])
    if rent_filter:
        query["monthly_rent"] = rent_filter
    if filters.get("min_bedrooms"):
        query["bedrooms"] = {"$gte": filters["min_bedrooms"]}
    if filters.get("move_in_date"):
        query["available_from"] = {"$lte": _mongo_date(filters["move_in_date"])}
    ordering = {
        "rent_low": [("monthly_rent", 1), ("created_at", -1)],
        "rent_high": [("monthly_rent", -1), ("created_at", -1)],
        "available": [("available_from", 1), ("created_at", -1)],
    }.get(sort, [("created_at", -1)])
    documents = get_database()["rentals_property"].find(query).sort(ordering)
    return [
        listing
        for document in documents
        if (listing := _property_from_document(document)) is not None
    ]


def count_visits_for_property(property_id):
    return get_database()["rentals_visitrequest"].count_documents(
        {"property_id": _parse_id(property_id)}
    )


def create_property_image(property_id, image_name):
    listing_id = _parse_id(property_id)
    image_name = validate_gallery_image(image_name)
    image = {
        "image_id": str(ObjectId()),
        "image": image_name,
        "created_at": datetime.now(datetime_timezone.utc),
    }
    result = get_database()["rentals_property"].update_one(
        {
            "_id": listing_id,
            "$expr": {
                "$lt": [
                    {"$size": {"$ifNull": ["$gallery", []]}},
                    8,
                ]
            },
        },
        {"$push": {"gallery": image}},
    )
    if result.matched_count != 1:
        if get_property(listing_id) is None:
            raise ValueError("The selected property no longer exists.")
        raise ValueError("A property can have no more than 8 additional photos.")
    return PropertyImage(
        image_id=image["image_id"],
        image=StoredFile(image_name),
        created_at=image["created_at"],
    )


def list_property_images(property_id):
    listing = get_property(property_id)
    return listing.gallery_images if listing else []


def delete_property_image(property_id, image_id):
    collection = get_database()["rentals_property"]
    listing = collection.find_one(
        {"_id": _parse_id(property_id), "gallery.image_id": image_id}
    )
    if listing is None:
        return None
    image_document = next(
        image for image in listing.get("gallery", [])
        if image.get("image_id") == image_id
    )
    collection.update_one(
        {"_id": listing["_id"]},
        {"$pull": {"gallery": {"image_id": image_id}}},
    )
    return PropertyImage(
        image_id=image_id,
        image=StoredFile(image_document.get("image", "")),
        created_at=image_document.get("created_at"),
    )


def get_image_count(property_id):
    listing = get_database()["rentals_property"].find_one(
        {"_id": _parse_id(property_id)},
        {"gallery": 1},
    )
    return len(listing.get("gallery", [])) if listing else 0


def saved_property_ids(renter_id):
    return {
        document["property_id"]
        for document in get_database()["rentals_savedproperty"].find(
            {"renter_id": _db_id(renter_id)},
            {"property_id": 1},
        )
    }


def list_saved_properties(renter_id):
    property_ids = saved_property_ids(renter_id)
    return [] if not property_ids else [
        listing
        for document in get_database()["rentals_property"].find(
            {
                "_id": {"$in": list(property_ids)},
                "status": Property.Status.PUBLISHED,
            }
        )
        for listing in [_property_from_document(document)]
        if listing is not None
    ]


def count_saved_properties(renter_id, property_id=None):
    query = {"renter_id": _db_id(renter_id)}
    if property_id is not None:
        query["property_id"] = _parse_id(property_id)
    return get_database()["rentals_savedproperty"].count_documents(query)


def set_saved_property(renter_id, property_id, save):
    renter = get_user(renter_id)
    listing = get_property(property_id, status=Property.Status.PUBLISHED)
    if renter is None or renter.role != User.Role.RENTER:
        raise ValueError("Only an active home seeker can save a listing.")
    if listing is None:
        raise ValueError("Only a published listing can be saved.")
    collection = get_database()["rentals_savedproperty"]
    query = {
        "renter_id": _db_id(renter_id),
        "property_id": _parse_id(property_id),
    }
    if save:
        collection.update_one(
            query,
            {"$setOnInsert": {**query, "created_at": datetime.now(datetime_timezone.utc)}},
            upsert=True,
        )
    else:
        collection.delete_one(query)


def create_visit(property_id, renter_id, scheduled_for, message=""):
    scheduled_for, message = validate_visit_data(scheduled_for, message)
    listing = get_property(property_id, status=Property.Status.PUBLISHED)
    renter = get_user(renter_id)
    if listing is None or renter is None or renter.role != User.Role.RENTER:
        raise ValueError("The selected listing or account no longer exists.")
    if listing.owner_id == renter.pk:
        raise ValueError("You cannot request a visit to your own property.")
    document = {
        "_id": ObjectId(),
        "property_id": listing.pk,
        "renter_id": renter.pk,
        "scheduled_for": _mongo_date(scheduled_for),
        "message": message,
        "status": VisitRequest.Status.REQUESTED,
        "created_at": datetime.now(datetime_timezone.utc),
        "updated_at": datetime.now(datetime_timezone.utc),
    }
    try:
        get_database()["rentals_visitrequest"].insert_one(document)
    except DuplicateKeyError as error:
        raise ValueError(
            "You already have an open visit request for this property. Cancel or finish it before requesting another."
        ) from error
    return _request_from_document(document, VisitRequest)


def list_visits(*, renter_id=None, owner_id=None):
    query = {}
    if renter_id is not None:
        query["renter_id"] = _db_id(renter_id)
    elif owner_id is not None:
        query.update(_request_owner_filter(owner_id))
    visits = [
        visit
        for document in get_database()["rentals_visitrequest"].find(query).sort("scheduled_for", 1)
        if (visit := _request_from_document(document, VisitRequest)) is not None
    ]
    return visits


def get_visit(visit_id, *, renter_id=None, owner_id=None, status=None):
    parsed_id = _parse_id(visit_id)
    if parsed_id is None:
        return None
    query = {"_id": parsed_id}
    if renter_id is not None:
        query["renter_id"] = _db_id(renter_id)
    if owner_id is not None:
        query.update(_request_owner_filter(owner_id))
    if isinstance(status, (list, tuple, set)):
        query["status"] = {"$in": list(status)}
    elif status is not None:
        query["status"] = status
    return _request_from_document(
        get_database()["rentals_visitrequest"].find_one(query),
        VisitRequest,
    )


def update_visit_status(visit_id, status):
    if status not in VisitRequest.Status.values:
        raise ValueError("Choose a valid visit status.")
    result = get_database()["rentals_visitrequest"].update_one(
        {"_id": _parse_id(visit_id)},
        {"$set": {"status": status, "updated_at": datetime.now(datetime_timezone.utc)}},
    )
    return result.modified_count == 1


def _overlapping_reservation_query(property_id, start_date, end_date, *, exclude_id=None):
    query = {
        "property_id": _parse_id(property_id),
        "status": {"$in": [Reservation.Status.REQUESTED, Reservation.Status.CONFIRMED]},
        "start_date": {"$lt": _mongo_date(end_date)},
        "end_date": {"$gt": _mongo_date(start_date)},
    }
    if exclude_id is not None:
        query["_id"] = {"$ne": _parse_id(exclude_id)}
    return query


def create_reservation(
    property_id,
    renter_id,
    start_date: date,
    end_date: date,
    message="",
):
    start_date, end_date, message = validate_reservation_data(
        start_date,
        end_date,
        message,
    )
    listing = get_property(property_id, status=Property.Status.PUBLISHED)
    renter = get_user(renter_id)
    if listing is None or renter is None or renter.role != User.Role.RENTER:
        raise ValueError("The selected listing or account no longer exists.")
    if listing.owner_id == renter.pk:
        raise ValueError("You cannot book your own property.")
    collection = get_database()["rentals_reservation"]
    if collection.find_one(
        _overlapping_reservation_query(listing.pk, start_date, end_date)
    ):
        raise ValueError(
            "These dates overlap another active booking request for this property."
        )
    document = {
        "_id": ObjectId(),
        "property_id": listing.pk,
        "renter_id": renter.pk,
        "start_date": _mongo_date(start_date),
        "end_date": _mongo_date(end_date),
        "message": message,
        "status": Reservation.Status.REQUESTED,
        "created_at": datetime.now(datetime_timezone.utc),
        "updated_at": datetime.now(datetime_timezone.utc),
    }
    collection.insert_one(document)
    return _request_from_document(document, Reservation)


def list_reservations(*, renter_id=None, owner_id=None):
    query = {}
    if renter_id is not None:
        query["renter_id"] = _db_id(renter_id)
    elif owner_id is not None:
        query.update(_request_owner_filter(owner_id))
    return [
        reservation
        for document in get_database()["rentals_reservation"].find(query).sort(
            [("start_date", 1), ("created_at", 1)]
        )
        if (reservation := _request_from_document(document, Reservation)) is not None
    ]


def get_reservation(reservation_id, *, renter_id=None, owner_id=None, status=None):
    parsed_id = _parse_id(reservation_id)
    if parsed_id is None:
        return None
    query = {"_id": parsed_id}
    if renter_id is not None:
        query["renter_id"] = _db_id(renter_id)
    if owner_id is not None:
        query.update(_request_owner_filter(owner_id))
    if isinstance(status, (list, tuple, set)):
        query["status"] = {"$in": list(status)}
    elif status is not None:
        query["status"] = status
    return _request_from_document(
        get_database()["rentals_reservation"].find_one(query),
        Reservation,
    )


def update_reservation_status(reservation_id, status):
    if status not in Reservation.Status.values:
        raise ValueError("Choose a valid booking status.")
    reservation = get_reservation(reservation_id)
    if reservation is None:
        return False
    collection = get_database()["rentals_reservation"]
    if status == Reservation.Status.CONFIRMED and collection.find_one(
        _overlapping_reservation_query(
            reservation.property.pk,
            reservation.start_date,
            reservation.end_date,
            exclude_id=reservation.pk,
        )
    ):
        raise ValueError(
            "These dates overlap another active booking request for this property."
        )
    result = collection.update_one(
        {"_id": reservation.pk},
        {"$set": {"status": status, "updated_at": datetime.now(datetime_timezone.utc)}},
    )
    return result.modified_count == 1
