from importlib import import_module
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase

from deliveryrecords.models import DailyDeliveryInputSnapshot, DeliveryRecord


def _load_seed_module(test_case: TestCase):
    try:
        return import_module("deliveryrecords.management.commands.seed_delivery_records")
    except ModuleNotFoundError as exc:
        test_case.fail(f"seed_delivery_records command module missing: {exc}")


class SeedDeliveryRecordsCommandTests(TestCase):
    def test_seed_command_creates_delivery_record_and_snapshot(self):
        seed_module = _load_seed_module(self)
        stdout = StringIO()

        call_command("seed_delivery_records", stdout=stdout)

        record = DeliveryRecord.objects.get(
            delivery_record_id=seed_module.SAMPLE_DELIVERY_RECORD_ID
        )
        snapshot = DailyDeliveryInputSnapshot.objects.get(
            daily_delivery_input_snapshot_id=seed_module.SAMPLE_DAILY_SNAPSHOT_ID
        )

        self.assertEqual(DeliveryRecord.objects.count(), 1)
        self.assertEqual(DailyDeliveryInputSnapshot.objects.count(), 1)
        self.assertEqual(record.company_id, seed_module.SAMPLE_COMPANY_ID)
        self.assertEqual(record.fleet_id, seed_module.SAMPLE_FLEET_ID)
        self.assertEqual(record.driver_id, seed_module.SAMPLE_DRIVER_ID)
        self.assertEqual(snapshot.company_id, seed_module.SAMPLE_COMPANY_ID)
        self.assertEqual(snapshot.fleet_id, seed_module.SAMPLE_FLEET_ID)
        self.assertEqual(snapshot.driver_id, seed_module.SAMPLE_DRIVER_ID)
        self.assertIn("Seeded delivery record bootstrap data.", stdout.getvalue())

    def test_seed_command_is_idempotent(self):
        seed_module = _load_seed_module(self)

        call_command("seed_delivery_records", stdout=StringIO())
        first_record = DeliveryRecord.objects.get(
            delivery_record_id=seed_module.SAMPLE_DELIVERY_RECORD_ID
        )
        first_snapshot = DailyDeliveryInputSnapshot.objects.get(
            daily_delivery_input_snapshot_id=seed_module.SAMPLE_DAILY_SNAPSHOT_ID
        )

        call_command("seed_delivery_records", stdout=StringIO())

        self.assertEqual(DeliveryRecord.objects.count(), 1)
        self.assertEqual(DailyDeliveryInputSnapshot.objects.count(), 1)
        self.assertEqual(
            DeliveryRecord.objects.get(
                delivery_record_id=seed_module.SAMPLE_DELIVERY_RECORD_ID
            ).pk,
            first_record.pk,
        )
        self.assertEqual(
            DailyDeliveryInputSnapshot.objects.get(
                daily_delivery_input_snapshot_id=seed_module.SAMPLE_DAILY_SNAPSHOT_ID
            ).pk,
            first_snapshot.pk,
        )

    def test_seed_command_reconciles_dirty_stack_rows_by_business_identity(self):
        seed_module = _load_seed_module(self)
        existing_record = DeliveryRecord.objects.create(
            delivery_record_id=uuid4(),
            company_id=seed_module.SAMPLE_COMPANY_ID,
            fleet_id=seed_module.SAMPLE_FLEET_ID,
            driver_id=seed_module.SAMPLE_DRIVER_ID,
            service_date=seed_module.SAMPLE_SERVICE_DATE,
            source_reference="seed-record-001",
            delivery_count=1,
            distance_km="1.00",
            base_amount="1000.00",
            status=DeliveryRecord.Status.DRAFT,
            payload={"source": "dirty"},
        )
        existing_snapshot = DailyDeliveryInputSnapshot.objects.create(
            daily_delivery_input_snapshot_id=uuid4(),
            company_id=seed_module.SAMPLE_COMPANY_ID,
            fleet_id=seed_module.SAMPLE_FLEET_ID,
            driver_id=seed_module.SAMPLE_DRIVER_ID,
            service_date=seed_module.SAMPLE_SERVICE_DATE,
            delivery_count=1,
            total_distance_km="1.00",
            total_base_amount="1000.00",
            source_record_count=99,
            status=DailyDeliveryInputSnapshot.Status.ACTIVE,
        )

        call_command("seed_delivery_records", stdout=StringIO())

        self.assertEqual(DeliveryRecord.objects.count(), 1)
        self.assertEqual(DailyDeliveryInputSnapshot.objects.count(), 1)
        self.assertEqual(
            DeliveryRecord.objects.get(
                company_id=seed_module.SAMPLE_COMPANY_ID,
                fleet_id=seed_module.SAMPLE_FLEET_ID,
                driver_id=seed_module.SAMPLE_DRIVER_ID,
                service_date=seed_module.SAMPLE_SERVICE_DATE,
                source_reference="seed-record-001",
            ).pk,
            existing_record.pk,
        )
        self.assertEqual(
            DailyDeliveryInputSnapshot.objects.get(
                company_id=seed_module.SAMPLE_COMPANY_ID,
                fleet_id=seed_module.SAMPLE_FLEET_ID,
                driver_id=seed_module.SAMPLE_DRIVER_ID,
                service_date=seed_module.SAMPLE_SERVICE_DATE,
                status=DailyDeliveryInputSnapshot.Status.ACTIVE,
            ).pk,
            existing_snapshot.pk,
        )

    def test_seed_command_reconciles_seed_record_uuid_collision(self):
        seed_module = _load_seed_module(self)

        DeliveryRecord.objects.create(
            delivery_record_id=seed_module.SAMPLE_DELIVERY_RECORD_ID,
            company_id=uuid4(),
            fleet_id=uuid4(),
            driver_id=uuid4(),
            service_date=seed_module.SAMPLE_SERVICE_DATE,
            source_reference="dirty-record",
            delivery_count=2,
            distance_km="2.00",
            base_amount="2000.00",
            status=DeliveryRecord.Status.DRAFT,
            payload={"source": "dirty"},
        )

        call_command("seed_delivery_records", stdout=StringIO())

        self.assertEqual(DeliveryRecord.objects.count(), 1)
        record = DeliveryRecord.objects.get(
            delivery_record_id=seed_module.SAMPLE_DELIVERY_RECORD_ID
        )
        self.assertEqual(record.company_id, seed_module.SAMPLE_COMPANY_ID)
        self.assertEqual(record.fleet_id, seed_module.SAMPLE_FLEET_ID)
        self.assertEqual(record.driver_id, seed_module.SAMPLE_DRIVER_ID)
        self.assertEqual(record.source_reference, "seed-record-001")

    def test_seed_command_reconciles_seed_snapshot_uuid_collision(self):
        seed_module = _load_seed_module(self)

        DailyDeliveryInputSnapshot.objects.create(
            daily_delivery_input_snapshot_id=seed_module.SAMPLE_DAILY_SNAPSHOT_ID,
            company_id=uuid4(),
            fleet_id=uuid4(),
            driver_id=uuid4(),
            service_date=seed_module.SAMPLE_SERVICE_DATE,
            delivery_count=2,
            total_distance_km="2.00",
            total_base_amount="2000.00",
            source_record_count=2,
            status=DailyDeliveryInputSnapshot.Status.ACTIVE,
        )

        call_command("seed_delivery_records", stdout=StringIO())

        self.assertEqual(DailyDeliveryInputSnapshot.objects.count(), 1)
        snapshot = DailyDeliveryInputSnapshot.objects.get(
            daily_delivery_input_snapshot_id=seed_module.SAMPLE_DAILY_SNAPSHOT_ID
        )
        self.assertEqual(snapshot.company_id, seed_module.SAMPLE_COMPANY_ID)
        self.assertEqual(snapshot.fleet_id, seed_module.SAMPLE_FLEET_ID)
        self.assertEqual(snapshot.driver_id, seed_module.SAMPLE_DRIVER_ID)
        self.assertEqual(snapshot.status, DailyDeliveryInputSnapshot.Status.ACTIVE)

    def test_seed_command_rolls_back_if_snapshot_write_fails(self):
        with patch(
            "deliveryrecords.management.commands.seed_delivery_records.Command._seed_daily_snapshot",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                call_command("seed_delivery_records", stdout=StringIO())

        self.assertEqual(DeliveryRecord.objects.count(), 0)
        self.assertEqual(DailyDeliveryInputSnapshot.objects.count(), 0)
