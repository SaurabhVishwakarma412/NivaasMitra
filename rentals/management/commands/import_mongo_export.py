import json
import shutil
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone

from rentals.models import Property, PropertyImage, Reservation, SavedProperty, User, VisitRequest


COLLECTIONS = (
    "users",
    "properties",
    "property_images",
    "saved_properties",
    "visit_requests",
    "reservations",
)


def decode_extended_json(value):
    if isinstance(value, list):
        return [decode_extended_json(item) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"$oid"}:
        return value["$oid"]
    if set(value) == {"$numberDecimal"}:
        return Decimal(value["$numberDecimal"])
    if set(value) == {"$numberInt"} or set(value) == {"$numberLong"}:
        return int(next(iter(value.values())))
    if set(value) == {"$numberDouble"}:
        return float(value["$numberDouble"])
    if set(value) == {"$date"}:
        date_value = value["$date"]
        if isinstance(date_value, dict) and "$numberLong" in date_value:
            return datetime.fromtimestamp(
                int(date_value["$numberLong"]) / 1000,
                tz=datetime_timezone.utc,
            )
        if isinstance(date_value, str):
            return datetime.fromisoformat(date_value.replace("Z", "+00:00"))
    return {key: decode_extended_json(item) for key, item in value.items()}


def read_export(path):
    with path.open(encoding="utf-8") as export:
        for line_number, line in enumerate(export, start=1):
            if not line.strip():
                continue
            try:
                document = decode_extended_json(json.loads(line))
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                raise CommandError(
                    f"Invalid Extended JSON in {path.name}, line {line_number}: {error}"
                ) from error
            if not isinstance(document, dict):
                raise CommandError(
                    f"Expected a JSON object in {path.name}, line {line_number}."
                )
            yield document


def document_id(document):
    value = document.get("_id")
    if value is None:
        raise CommandError("A MongoDB export document has no _id.")
    return str(value)


class Command(BaseCommand):
    help = (
        "Import MongoDB Extended JSON exports into the Django database. "
        "This command does not connect to or modify MongoDB."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--directory",
            required=True,
            help="Directory containing one JSON-lines export per collection.",
        )
        parser.add_argument(
            "--media-source",
            help="Optional directory containing the old MEDIA_ROOT files.",
        )

    def handle(self, *args, **options):
        export_directory = Path(options["directory"]).resolve()
        export_paths = {
            collection: export_directory / f"{collection}.json"
            for collection in COLLECTIONS
        }
        missing = [path.name for path in export_paths.values() if not path.is_file()]
        if missing:
            raise CommandError(
                "Missing required export files: " + ", ".join(missing)
            )

        media_source = (
            Path(options["media_source"]).resolve()
            if options.get("media_source")
            else None
        )
        imported = {collection: 0 for collection in COLLECTIONS}
        user_ids = {}
        property_ids = {}

        try:
            with transaction.atomic():
                for document in read_export(export_paths["users"]):
                    source_id = document_id(document)
                    username = document["username"].strip().lower()
                    user, _ = User.objects.update_or_create(
                        username=username,
                        defaults={
                            "email": document.get("email", "").strip().lower(),
                            "first_name": document.get("first_name", ""),
                            "last_name": document.get("last_name", ""),
                            "role": document["role"],
                            "password": document["password_hash"],
                            "is_active": document.get("is_active", True),
                            "is_staff": document.get("is_staff", False),
                            "is_superuser": document.get("is_superuser", False),
                            "date_joined": document.get("created_at", timezone.now()),
                        },
                    )
                    user_ids[source_id] = user.pk
                    imported["users"] += 1

                for document in read_export(export_paths["properties"]):
                    source_id = document_id(document)
                    owner_id = user_ids.get(str(document["owner_id"]))
                    if owner_id is None:
                        raise CommandError(
                            f"Property {source_id} refers to an unimported owner."
                        )
                    listing, _ = Property.objects.update_or_create(
                        pk=source_id,
                        defaults={
                            "owner_id": owner_id,
                            "title": document["title"],
                            "description": document["description"],
                            "property_type": document["property_type"],
                            "monthly_rent": document["monthly_rent"],
                            "security_deposit": document["security_deposit"],
                            "address": document["address"],
                            "city": document["city"],
                            "state": document["state"],
                            "postal_code": document["postal_code"],
                            "bedrooms": document["bedrooms"],
                            "bathrooms": document["bathrooms"],
                            "available_from": document["available_from"],
                            "status": document["status"],
                            "cover_image": document.get("cover_image", ""),
                        },
                    )
                    property_ids[source_id] = listing.pk
                    imported["properties"] += 1
                    self._copy_media(
                        document.get("cover_image", ""),
                        media_source,
                    )
                    self._restore_timestamps(
                        Property,
                        listing.pk,
                        document,
                    )

                for document in read_export(export_paths["property_images"]):
                    source_id = document_id(document)
                    property_id = property_ids.get(str(document["property_id"]))
                    if property_id is None:
                        raise CommandError(
                            f"Gallery image {source_id} refers to an unimported property."
                        )
                    image, _ = PropertyImage.objects.update_or_create(
                        pk=source_id,
                        defaults={
                            "property_id": property_id,
                            "image": document["image"],
                        },
                    )
                    imported["property_images"] += 1
                    self._restore_timestamps(PropertyImage, image.pk, document)
                    self._copy_media(document.get("image", ""), media_source)

                for document in read_export(export_paths["saved_properties"]):
                    renter_id = user_ids.get(str(document["renter_id"]))
                    property_id = property_ids.get(str(document["property_id"]))
                    if renter_id is None or property_id is None:
                        raise CommandError(
                            "A saved property refers to a user or listing that was not imported."
                        )
                    SavedProperty.objects.get_or_create(
                        renter_id=renter_id,
                        property_id=property_id,
                    )
                    imported["saved_properties"] += 1

                for document in read_export(export_paths["visit_requests"]):
                    source_id = document_id(document)
                    renter_id = user_ids.get(str(document["renter_id"]))
                    property_id = property_ids.get(str(document["property_id"]))
                    if renter_id is None or property_id is None:
                        raise CommandError(
                            f"Visit {source_id} refers to an unimported user or property."
                        )
                    visit, _ = VisitRequest.objects.update_or_create(
                        pk=source_id,
                        defaults={
                            "renter_id": renter_id,
                            "property_id": property_id,
                            "scheduled_for": document["scheduled_for"],
                            "message": document.get("message", ""),
                            "status": document["status"],
                        },
                    )
                    imported["visit_requests"] += 1
                    self._restore_timestamps(VisitRequest, visit.pk, document)

                for document in read_export(export_paths["reservations"]):
                    source_id = document_id(document)
                    renter_id = user_ids.get(str(document["renter_id"]))
                    property_id = property_ids.get(str(document["property_id"]))
                    if renter_id is None or property_id is None:
                        raise CommandError(
                            f"Reservation {source_id} refers to an unimported user or property."
                        )
                    reservation, _ = Reservation.objects.update_or_create(
                        pk=source_id,
                        defaults={
                            "renter_id": renter_id,
                            "property_id": property_id,
                            "start_date": document["start_date"],
                            "end_date": document["end_date"],
                            "message": document.get("message", ""),
                            "status": document["status"],
                        },
                    )
                    imported["reservations"] += 1
                    self._restore_timestamps(Reservation, reservation.pk, document)
        except (IntegrityError, KeyError, TypeError, ValueError) as error:
            raise CommandError(f"Could not import MongoDB export: {error}") from error

        for collection, count in imported.items():
            self.stdout.write(f"{collection}: {count}")
        self.stdout.write(
            self.style.SUCCESS("Import completed. MongoDB source data was not modified.")
        )

    @staticmethod
    def _restore_timestamps(model, pk, document):
        values = {}
        for field in ("created_at", "updated_at"):
            if field in document:
                values[field] = document[field]
        if values:
            model.objects.filter(pk=pk).update(**values)

    @staticmethod
    def _copy_media(name, media_source):
        if not name or media_source is None:
            return
        relative_path = Path(name)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise CommandError(f"Unsafe media path in export: {name}")
        source = (media_source / relative_path).resolve()
        target_root = Path(settings.MEDIA_ROOT).resolve()
        target = (target_root / relative_path).resolve()
        if media_source not in source.parents or target_root not in target.parents:
            raise CommandError(f"Unsafe media path in export: {name}")
        if not source.is_file():
            raise CommandError(f"Missing exported media file: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
