from datetime import date
from decimal import Decimal
from uuid import UUID

from django.core.management.base import BaseCommand
from django.db import transaction

from deliveryrecords.models import DailyDeliveryInputSnapshot, DeliveryRecord

SAMPLE_DELIVERY_RECORD_ID = UUID("84000000-0000-0000-0000-000000000001")
SAMPLE_DAILY_SNAPSHOT_ID = UUID("84000000-0000-0000-0000-000000000002")
SAMPLE_COMPANY_ID = UUID("30000000-0000-0000-0000-000000000001")
SAMPLE_FLEET_ID = UUID("40000000-0000-0000-0000-000000000001")
SAMPLE_DRIVER_ID = UUID("10000000-0000-0000-0000-000000000001")
SAMPLE_SERVICE_DATE = date(2026, 3, 24)


class Command(BaseCommand):
    help = "Seed deterministic delivery record bootstrap data."

    def handle(self, *args, **options):
        with transaction.atomic():
            self._seed_delivery_record()
            self._seed_daily_snapshot()
        self.stdout.write(self.style.SUCCESS("Seeded delivery record bootstrap data."))

    def _seed_delivery_record(self):
        record = DeliveryRecord.objects.filter(
            company_id=SAMPLE_COMPANY_ID,
            fleet_id=SAMPLE_FLEET_ID,
            driver_id=SAMPLE_DRIVER_ID,
            service_date=SAMPLE_SERVICE_DATE,
            source_reference="seed-record-001",
        ).first()
        if record is None:
            record = DeliveryRecord.objects.filter(
                delivery_record_id=SAMPLE_DELIVERY_RECORD_ID
            ).first()
        if record is None:
            return DeliveryRecord.objects.create(
                delivery_record_id=SAMPLE_DELIVERY_RECORD_ID,
                company_id=SAMPLE_COMPANY_ID,
                fleet_id=SAMPLE_FLEET_ID,
                driver_id=SAMPLE_DRIVER_ID,
                service_date=SAMPLE_SERVICE_DATE,
                source_reference="seed-record-001",
                delivery_count=8,
                distance_km=Decimal("18.40"),
                base_amount=Decimal("72000.00"),
                status=DeliveryRecord.Status.CONFIRMED,
                payload={
                    "source": "bootstrap",
                    "note": "Seed delivery record for local stack.",
                },
            )

        record.company_id = SAMPLE_COMPANY_ID
        record.fleet_id = SAMPLE_FLEET_ID
        record.driver_id = SAMPLE_DRIVER_ID
        record.service_date = SAMPLE_SERVICE_DATE
        record.source_reference = "seed-record-001"
        record.delivery_count = 8
        record.distance_km = Decimal("18.40")
        record.base_amount = Decimal("72000.00")
        record.status = DeliveryRecord.Status.CONFIRMED
        record.payload = {
            "source": "bootstrap",
            "note": "Seed delivery record for local stack.",
        }
        record.save(
            update_fields=[
                "company_id",
                "fleet_id",
                "driver_id",
                "service_date",
                "source_reference",
                "delivery_count",
                "distance_km",
                "base_amount",
                "status",
                "payload",
            ]
        )
        return record

    def _seed_daily_snapshot(self):
        snapshot = DailyDeliveryInputSnapshot.objects.filter(
            company_id=SAMPLE_COMPANY_ID,
            fleet_id=SAMPLE_FLEET_ID,
            driver_id=SAMPLE_DRIVER_ID,
            service_date=SAMPLE_SERVICE_DATE,
            status=DailyDeliveryInputSnapshot.Status.ACTIVE,
        ).first()
        if snapshot is None:
            snapshot = DailyDeliveryInputSnapshot.objects.filter(
                daily_delivery_input_snapshot_id=SAMPLE_DAILY_SNAPSHOT_ID
            ).first()
        if snapshot is None:
            return DailyDeliveryInputSnapshot.objects.create(
                daily_delivery_input_snapshot_id=SAMPLE_DAILY_SNAPSHOT_ID,
                company_id=SAMPLE_COMPANY_ID,
                fleet_id=SAMPLE_FLEET_ID,
                driver_id=SAMPLE_DRIVER_ID,
                service_date=SAMPLE_SERVICE_DATE,
                delivery_count=8,
                total_distance_km=Decimal("18.40"),
                total_base_amount=Decimal("72000.00"),
                source_record_count=1,
                status=DailyDeliveryInputSnapshot.Status.ACTIVE,
            )

        snapshot.company_id = SAMPLE_COMPANY_ID
        snapshot.fleet_id = SAMPLE_FLEET_ID
        snapshot.driver_id = SAMPLE_DRIVER_ID
        snapshot.service_date = SAMPLE_SERVICE_DATE
        snapshot.delivery_count = 8
        snapshot.total_distance_km = Decimal("18.40")
        snapshot.total_base_amount = Decimal("72000.00")
        snapshot.source_record_count = 1
        snapshot.status = DailyDeliveryInputSnapshot.Status.ACTIVE
        snapshot.save(
            update_fields=[
                "company_id",
                "fleet_id",
                "driver_id",
                "service_date",
                "delivery_count",
                "total_distance_km",
                "total_base_amount",
                "source_record_count",
                "status",
            ]
        )
        return snapshot
