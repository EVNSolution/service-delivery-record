import json
import tempfile
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase

from deliveryrecords.models import DailyDeliveryInputSnapshot, DeliveryRecord


class ImportOpsFixtureCommandTests(TestCase):
    def test_command_imports_delivery_records_and_snapshots(self):
        payload = {
            "delivery_records": {
                "records": [
                    {
                        "delivery_record_id": str(uuid4()),
                        "company_id": str(uuid4()),
                        "fleet_id": str(uuid4()),
                        "driver_id": str(uuid4()),
                        "service_date": "2026-03-30",
                        "source_reference": "ops-fixture-1",
                        "delivery_count": 10,
                        "distance_km": "18.25",
                        "base_amount": "72000.00",
                        "status": "confirmed",
                        "payload": {"source": "ops-derived-fixture"},
                    }
                ],
                "snapshots": [
                    {
                        "daily_delivery_input_snapshot_id": str(uuid4()),
                        "company_id": str(uuid4()),
                        "fleet_id": str(uuid4()),
                        "driver_id": str(uuid4()),
                        "service_date": "2026-03-30",
                        "delivery_count": 10,
                        "total_distance_km": "18.25",
                        "total_base_amount": "72000.00",
                        "source_record_count": 1,
                        "status": "active",
                    }
                ],
            }
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            Path(tmp.name).write_text(json.dumps(payload))
            fixture_path = tmp.name
        self.addCleanup(Path(fixture_path).unlink, missing_ok=True)

        call_command("import_ops_fixture", "--fixture", fixture_path, stdout=Mock())
        call_command("import_ops_fixture", "--fixture", fixture_path, stdout=Mock())

        self.assertEqual(DeliveryRecord.objects.count(), 1)
        self.assertEqual(DailyDeliveryInputSnapshot.objects.count(), 1)
