import json
from pathlib import Path
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date

from deliveryrecords.models import DailyDeliveryInputSnapshot, DeliveryRecord


class Command(BaseCommand):
    help = "Import the delivery-record section from an ops-derived local fixture."

    def add_arguments(self, parser):
        parser.add_argument("--fixture", required=True, help="Absolute path to the fixture JSON file.")

    def handle(self, *args, **options):
        payload = self._load_fixture(options["fixture"])
        delivery_payload = payload.get("delivery_records", {})
        imported_records = 0
        imported_snapshots = 0

        with transaction.atomic():
            for record_payload in delivery_payload.get("records", []):
                DeliveryRecord.objects.update_or_create(
                    delivery_record_id=UUID(record_payload["delivery_record_id"]),
                    defaults={
                        "company_id": UUID(record_payload["company_id"]),
                        "fleet_id": UUID(record_payload["fleet_id"]),
                        "driver_id": UUID(record_payload["driver_id"]),
                        "service_date": parse_date(record_payload["service_date"]),
                        "source_reference": record_payload["source_reference"],
                        "delivery_count": record_payload["delivery_count"],
                        "distance_km": record_payload["distance_km"],
                        "base_amount": record_payload["base_amount"],
                        "status": record_payload["status"],
                        "payload": record_payload["payload"],
                    },
                )
                imported_records += 1

            for snapshot_payload in delivery_payload.get("snapshots", []):
                DailyDeliveryInputSnapshot.objects.update_or_create(
                    daily_delivery_input_snapshot_id=UUID(
                        snapshot_payload["daily_delivery_input_snapshot_id"]
                    ),
                    defaults={
                        "company_id": UUID(snapshot_payload["company_id"]),
                        "fleet_id": UUID(snapshot_payload["fleet_id"]),
                        "driver_id": UUID(snapshot_payload["driver_id"]),
                        "service_date": parse_date(snapshot_payload["service_date"]),
                        "delivery_count": snapshot_payload["delivery_count"],
                        "total_distance_km": snapshot_payload["total_distance_km"],
                        "total_base_amount": snapshot_payload["total_base_amount"],
                        "source_record_count": snapshot_payload["source_record_count"],
                        "status": snapshot_payload["status"],
                    },
                )
                imported_snapshots += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Imported ops-derived delivery fixture "
                f"({imported_records} records, {imported_snapshots} snapshots)."
            )
        )

    def _load_fixture(self, fixture_path: str) -> dict:
        path = Path(fixture_path)
        if not path.exists():
            raise CommandError(f"Fixture file does not exist: {path}")
        return json.loads(path.read_text())
