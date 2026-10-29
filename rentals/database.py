from functools import lru_cache

from django.conf import settings
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid

from .validation import MONGO_COLLECTION_VALIDATORS


@lru_cache(maxsize=4)
def _client(uri):
    return MongoClient(uri, appname="NivaasMitra")


def get_database():
    _ensure_indexes(settings.MONGODB_URI, settings.MONGODB_NAME)
    return _client(settings.MONGODB_URI)[settings.MONGODB_NAME]


@lru_cache(maxsize=4)
def _ensure_indexes(uri, name):
    database = _client(uri)[name]
    collection_names = set(database.list_collection_names())
    for collection_name, validator in MONGO_COLLECTION_VALIDATORS.items():
        if collection_name not in collection_names:
            try:
                database.create_collection(
                    collection_name,
                    validator=validator,
                    validationLevel="strict",
                    validationAction="error",
                )
            except CollectionInvalid:
                pass
        database.command(
            {
                "collMod": collection_name,
                "validator": validator,
                "validationLevel": "strict",
                "validationAction": "error",
            }
        )

    database["rentals_user"].create_index("username", unique=True)
    database["rentals_user"].create_index("email", unique=True)
    database["rentals_property"].create_index([("status", 1), ("city", 1)])
    database["rentals_property"].create_index([("owner_id", 1), ("created_at", -1)])
    database["rentals_savedproperty"].create_index(
        [("renter_id", 1), ("property_id", 1)],
        unique=True,
    )
    database["rentals_visitrequest"].create_index(
        [("property_id", 1), ("renter_id", 1)],
        unique=True,
        partialFilterExpression={"status": {"$in": ["requested", "confirmed"]}},
    )
    database["rentals_visitrequest"].create_index([("scheduled_for", 1)])
    database["rentals_reservation"].create_index([("property_id", 1), ("start_date", 1)])
    database["rentals_reservation"].create_index([("renter_id", 1), ("start_date", 1)])
    database["django_session"].create_index("expire_date", expireAfterSeconds=0)
