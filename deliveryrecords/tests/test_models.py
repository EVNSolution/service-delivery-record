from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from importlib import import_module
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase


class _PytestShim:
    @contextmanager
    def raises(self, expected_exception):
        try:
            yield
        except expected_exception:
            return
        raise AssertionError(f"{expected_exception.__name__} was not raised")


pytest = _PytestShim()


def _load_models_module(test_case: TestCase):
    try:
        return import_module("deliveryrecords.models")
    except ModuleNotFoundError as exc:
        test_case.fail(f"deliveryrecords.models module missing: {exc}")


class DeliveryRecordModelTests(TestCase):
    def setUp(self) -> None:
        self.company_id = uuid4()
        self.fleet_id = uuid4()
        self.driver_id = uuid4()
        self.service_date = date(2026, 3, 24)

    def _create_delivery_record(self, models_module, **overrides):
        defaults = {
            "company_id": self.company_id,
            "fleet_id": self.fleet_id,
            "driver_id": self.driver_id,
            "service_date": self.service_date,
            "source_reference": "source-001",
            "delivery_count": 12,
            "distance_km": Decimal("25.50"),
            "base_amount": Decimal("120000.00"),
            "status": models_module.DeliveryRecord.Status.CONFIRMED,
            "payload": {"batch": "alpha"},
        }
        defaults.update(overrides)
        return models_module.DeliveryRecord.objects.create(**defaults)

    def test_delivery_record_can_be_created_and_loaded(self):
        models_module = _load_models_module(self)

        record = self._create_delivery_record(models_module)
        loaded = models_module.DeliveryRecord.objects.get(pk=record.pk)

        self.assertEqual(loaded.company_id, self.company_id)
        self.assertEqual(loaded.fleet_id, self.fleet_id)
        self.assertEqual(loaded.driver_id, self.driver_id)
        self.assertEqual(loaded.service_date, self.service_date)
        self.assertEqual(loaded.source_reference, "source-001")
        self.assertEqual(loaded.delivery_count, 12)
        self.assertEqual(loaded.distance_km, Decimal("25.50"))
        self.assertEqual(loaded.base_amount, Decimal("120000.00"))
        self.assertEqual(loaded.status, models_module.DeliveryRecord.Status.CONFIRMED)
        self.assertEqual(loaded.payload, {"batch": "alpha"})

    def test_delivery_record_source_reference_is_unique_within_scope_and_service_date(self):
        models_module = _load_models_module(self)
        self._create_delivery_record(models_module)

        duplicate = models_module.DeliveryRecord(
            company_id=self.company_id,
            fleet_id=self.fleet_id,
            driver_id=self.driver_id,
            service_date=self.service_date,
            source_reference="source-001",
            delivery_count=9,
            distance_km=Decimal("20.00"),
            base_amount=Decimal("90000.00"),
            status=models_module.DeliveryRecord.Status.DRAFT,
            payload={"batch": "beta"},
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_delivery_record_duplicate_insert_is_rejected_by_the_database(self):
        models_module = _load_models_module(self)
        self._create_delivery_record(models_module)

        with self.assertRaises(IntegrityError):
            self._create_delivery_record(models_module)

    def test_delivery_record_rejects_negative_numeric_fields(self):
        models_module = _load_models_module(self)

        invalid_cases = (
            {"delivery_count": -1},
            {"distance_km": Decimal("-0.01")},
            {"base_amount": Decimal("-1.00")},
        )

        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                params = {
                    "company_id": self.company_id,
                    "fleet_id": self.fleet_id,
                    "driver_id": self.driver_id,
                    "service_date": self.service_date,
                    "source_reference": "source-002",
                    "delivery_count": 12,
                    "distance_km": Decimal("25.50"),
                    "base_amount": Decimal("120000.00"),
                    "status": models_module.DeliveryRecord.Status.DRAFT,
                    "payload": {"batch": "gamma"},
                }
                params.update(overrides)
                record = models_module.DeliveryRecord(**params)

                with self.assertRaises(ValidationError):
                    record.full_clean()


class DailyDeliveryInputSnapshotModelTests(TestCase):
    def setUp(self) -> None:
        self.company_id = uuid4()
        self.fleet_id = uuid4()
        self.driver_id = uuid4()
        self.service_date = date(2026, 3, 24)

    def _create_snapshot(self, models_module, **overrides):
        defaults = {
            "company_id": self.company_id,
            "fleet_id": self.fleet_id,
            "driver_id": self.driver_id,
            "service_date": self.service_date,
            "delivery_count": 12,
            "total_distance_km": Decimal("25.50"),
            "total_base_amount": Decimal("120000.00"),
            "source_record_count": 12,
            "status": models_module.DailyDeliveryInputSnapshot.Status.ACTIVE,
        }
        defaults.update(overrides)
        return models_module.DailyDeliveryInputSnapshot.objects.create(**defaults)

    def test_daily_delivery_input_snapshot_can_be_created_and_loaded(self):
        models_module = _load_models_module(self)

        snapshot = self._create_snapshot(models_module)
        loaded = models_module.DailyDeliveryInputSnapshot.objects.get(pk=snapshot.pk)

        self.assertEqual(loaded.company_id, self.company_id)
        self.assertEqual(loaded.fleet_id, self.fleet_id)
        self.assertEqual(loaded.driver_id, self.driver_id)
        self.assertEqual(loaded.service_date, self.service_date)
        self.assertEqual(loaded.delivery_count, 12)
        self.assertEqual(loaded.total_distance_km, Decimal("25.50"))
        self.assertEqual(loaded.total_base_amount, Decimal("120000.00"))
        self.assertEqual(loaded.source_record_count, 12)
        self.assertEqual(
            loaded.status,
            models_module.DailyDeliveryInputSnapshot.Status.ACTIVE,
        )

    def test_daily_delivery_input_snapshot_rejects_negative_numeric_fields(self):
        models_module = _load_models_module(self)

        invalid_cases = (
            {"delivery_count": -1},
            {"total_distance_km": Decimal("-0.01")},
            {"total_base_amount": Decimal("-1.00")},
            {"source_record_count": -1},
        )

        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                params = {
                    "company_id": self.company_id,
                    "fleet_id": self.fleet_id,
                    "driver_id": self.driver_id,
                    "service_date": self.service_date,
                    "delivery_count": 12,
                    "total_distance_km": Decimal("25.50"),
                    "total_base_amount": Decimal("120000.00"),
                    "source_record_count": 12,
                    "status": models_module.DailyDeliveryInputSnapshot.Status.ACTIVE,
                }
                params.update(overrides)
                snapshot = models_module.DailyDeliveryInputSnapshot(**params)

                with self.assertRaises(ValidationError):
                    snapshot.full_clean()

    def test_superseded_snapshots_can_repeat_for_same_scope_and_service_date(self):
        models_module = _load_models_module(self)

        first_snapshot = self._create_snapshot(
            models_module,
            status=models_module.DailyDeliveryInputSnapshot.Status.SUPERSEDED,
        )
        second_snapshot = self._create_snapshot(
            models_module,
            source_record_count=11,
            status=models_module.DailyDeliveryInputSnapshot.Status.SUPERSEDED,
        )

        self.assertNotEqual(first_snapshot.pk, second_snapshot.pk)
        self.assertEqual(
            models_module.DailyDeliveryInputSnapshot.objects.filter(
                company_id=self.company_id,
                fleet_id=self.fleet_id,
                driver_id=self.driver_id,
                service_date=self.service_date,
                status=models_module.DailyDeliveryInputSnapshot.Status.SUPERSEDED,
            ).count(),
            2,
        )

    def test_active_snapshot_duplicate_insert_is_rejected_by_the_database(self):
        models_module = _load_models_module(self)
        self._create_snapshot(models_module)

        with self.assertRaises(IntegrityError):
            self._create_snapshot(models_module)

    def test_active_snapshot_is_unique_per_scope_and_service_date(self):
        models_module = _load_models_module(self)
        self._create_snapshot(models_module)

        duplicate = models_module.DailyDeliveryInputSnapshot(
            company_id=self.company_id,
            fleet_id=self.fleet_id,
            driver_id=self.driver_id,
            service_date=self.service_date,
            delivery_count=9,
            total_distance_km=Decimal("20.00"),
            total_base_amount=Decimal("90000.00"),
            source_record_count=9,
            status=models_module.DailyDeliveryInputSnapshot.Status.ACTIVE,
        )

        with pytest.raises(ValidationError):
            duplicate.full_clean()
