from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connections, transaction

from rentals.models import (
    Property,
    PropertyImage,
    Reservation,
    SavedProperty,
    User,
    VisitRequest,
)


MODEL_ORDER = (
    User,
    Property,
    PropertyImage,
    SavedProperty,
    VisitRequest,
    Reservation,
)
SOURCE_ALIAS = "sqlite_import_source"


class Command(BaseCommand):
    help = (
        "Copy rental records from the existing db.sqlite3 into PostgreSQL "
        "without modifying the SQLite source."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="db.sqlite3",
            help="Path to the source SQLite database (default: db.sqlite3).",
        )

    def handle(self, *args, **options):
        source_path = Path(options["source"]).resolve()
        if not source_path.is_file():
            raise CommandError(f"SQLite source database does not exist: {source_path}")
        if SOURCE_ALIAS in connections.databases:
            raise CommandError(f"Database alias {SOURCE_ALIAS!r} is already configured.")

        source_database = connections.databases["default"].copy()
        source_database.update(
            {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(source_path),
                "CONN_MAX_AGE": 0,
            }
        )
        connections.databases[SOURCE_ALIAS] = source_database
        source_connection = connections[SOURCE_ALIAS]
        imported = {model._meta.label: 0 for model in MODEL_ORDER}

        try:
            with transaction.atomic(using="default"):
                populated_models = [
                    model._meta.label
                    for model in MODEL_ORDER
                    if model.objects.using("default").exists()
                ]
                if populated_models:
                    raise CommandError(
                        "The PostgreSQL rentals tables must be empty before import. "
                        "Already populated: " + ", ".join(populated_models)
                    )

                for model in MODEL_ORDER:
                    records = model.objects.using(SOURCE_ALIAS).all()
                    serialized = serializers.serialize("json", records)
                    for record in serializers.deserialize(
                        "json",
                        serialized,
                        using="default",
                    ):
                        record.save(using="default")
                        imported[model._meta.label] += 1

                reset_sql = connections["default"].ops.sequence_reset_sql(
                    no_style(),
                    list(MODEL_ORDER),
                )
                with connections["default"].cursor() as cursor:
                    for statement in reset_sql:
                        cursor.execute(statement)
        finally:
            source_connection.close()
            del connections.databases[SOURCE_ALIAS]

        for model_label, count in imported.items():
            self.stdout.write(f"{model_label}: {count}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {sum(imported.values())} records. "
                "The SQLite source database was not modified."
            )
        )
