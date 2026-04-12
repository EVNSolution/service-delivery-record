from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import jwt
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from deliveryrecords.models import DailyDeliveryInputSnapshot, DeliveryRecord


class DeliveryRecordApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.admin_token = self._issue_token(role="admin")
        self.user_token = self._issue_token(role="user")
        self.company_id = str(uuid4())
        self.fleet_id = str(uuid4())
        self.driver_id = str(uuid4())
        self.service_date = "2026-03-24"

    def _issue_token(self, *, role: str, allowed_nav_keys: list[str] | None = None) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(uuid4()),
            "email": f"{role}@example.com",
            "role": role,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "jti": str(uuid4()),
            "type": "access",
        }
        if allowed_nav_keys is not None:
            payload["allowed_nav_keys"] = allowed_nav_keys
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def _admin_client(self) -> APIClient:
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        return client

    def _user_client(self) -> APIClient:
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        return client

    def _admin_client_with_nav_keys(self, *allowed_nav_keys: str) -> APIClient:
        client = APIClient()
        token = self._issue_token(role="admin", allowed_nav_keys=list(allowed_nav_keys))
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    def _record_payload(self, *, source_reference: str = "record-001") -> dict:
        return {
            "company_id": self.company_id,
            "fleet_id": self.fleet_id,
            "driver_id": self.driver_id,
            "service_date": self.service_date,
            "source_reference": source_reference,
            "delivery_count": 12,
            "distance_km": "25.50",
            "base_amount": "120000.00",
            "status": DeliveryRecord.Status.CONFIRMED,
            "payload": {"batch": "alpha"},
        }

    def _snapshot_payload(self) -> dict:
        return {
            "company_id": self.company_id,
            "fleet_id": self.fleet_id,
            "driver_id": self.driver_id,
            "service_date": self.service_date,
            "delivery_count": 12,
            "total_distance_km": "25.50",
            "total_base_amount": "120000.00",
            "source_record_count": 12,
            "status": DailyDeliveryInputSnapshot.Status.ACTIVE,
        }

    def _build_json_response(self, payload: str):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = payload.encode("utf-8")
        return response

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_non_admin_access_is_rejected_for_records_crud(self) -> None:
        client = self._user_client()
        record_id = str(uuid4())
        snapshot_id = str(uuid4())

        read_responses = (
            client.get("/records/"),
            client.get("/daily-snapshots/"),
        )
        write_responses = (
            client.post("/records/", self._record_payload(), format="json"),
            client.patch(f"/records/{record_id}/", {"delivery_count": 99}, format="json"),
            client.post("/daily-snapshots/", self._snapshot_payload(), format="json"),
            client.patch(f"/daily-snapshots/{snapshot_id}/", {"delivery_count": 99}, format="json"),
        )

        self.assertTrue(all(response.status_code == 200 for response in read_responses))
        self.assertTrue(all(response.status_code == 403 for response in write_responses))

    def test_admin_without_dispatch_or_settlements_nav_key_is_denied(self) -> None:
        client = self._admin_client_with_nav_keys("vehicles")

        record_list_response = client.get("/records/")
        snapshot_list_response = client.get("/daily-snapshots/")

        self.assertEqual(record_list_response.status_code, 403)
        self.assertEqual(snapshot_list_response.status_code, 403)

    def test_admin_with_dispatch_nav_key_can_read_delivery_records(self) -> None:
        client = self._admin_client_with_nav_keys("dispatch")

        self.assertEqual(client.get("/records/").status_code, 200)
        self.assertEqual(client.get("/daily-snapshots/").status_code, 200)

    def test_admin_with_settlements_nav_key_can_read_delivery_records(self) -> None:
        client = self._admin_client_with_nav_keys("settlements")

        self.assertEqual(client.get("/records/").status_code, 200)
        self.assertEqual(client.get("/daily-snapshots/").status_code, 200)

    def test_admin_can_post_records_and_get_201(self) -> None:
        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            response = self._admin_client().post("/records/", self._record_payload(), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["source_reference"], "record-001")
        self.assertEqual(response.data["status"], DeliveryRecord.Status.CONFIRMED)

    @patch("deliveryrecords.services.source_clients.urlopen")
    def test_admin_can_post_records_through_live_source_validation_contract(self, mocked_urlopen) -> None:
        mocked_urlopen.side_effect = [
            self._build_json_response(
                f'{{"company_id":"{self.company_id}","name":"Seed Company"}}'
            ),
            self._build_json_response(
                f'{{"fleet_id":"{self.fleet_id}","company_id":"{self.company_id}","name":"Seed Fleet"}}'
            ),
            self._build_json_response(
                f'{{"driver_id":"{self.driver_id}","company_id":"{self.company_id}","fleet_id":"{self.fleet_id}"}}'
            ),
        ]

        response = self._admin_client().post("/records/", self._record_payload(), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            mocked_urlopen.call_args_list[2].args[0].full_url,
            f"{settings.DRIVER_PROFILE_BASE_URL.rstrip('/')}/{self.driver_id}/",
        )

    def test_admin_can_crud_records(self) -> None:
        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            create_response = self._admin_client().post("/records/", self._record_payload(), format="json")

        record_id = create_response.data["delivery_record_id"]

        list_response = self._admin_client().get("/records/")
        detail_response = self._admin_client().get(f"/records/{record_id}/")

        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            update_response = self._admin_client().patch(
                f"/records/{record_id}/",
                {"delivery_count": 15},
                format="json",
            )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(update_response.status_code, 200)

    def test_record_list_supports_driver_id_and_status_filters(self) -> None:
        other_driver_id = str(uuid4())
        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            self._admin_client().post("/records/", self._record_payload(source_reference="record-001"), format="json")
            self._admin_client().post(
                "/records/",
                {
                    **self._record_payload(source_reference="record-002"),
                    "status": DeliveryRecord.Status.DRAFT,
                },
                format="json",
            )
            self._admin_client().post(
                "/records/",
                {
                    **self._record_payload(source_reference="record-003"),
                    "driver_id": other_driver_id,
                },
                format="json",
            )

        response = self._user_client().get(
            f"/records/?driver_id={self.driver_id}&status={DeliveryRecord.Status.CONFIRMED}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["source_reference"], "record-001")

    def test_record_list_supports_company_and_fleet_filters(self) -> None:
        other_company_id = str(uuid4())
        other_fleet_id = str(uuid4())

        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            self._admin_client().post("/records/", self._record_payload(source_reference="record-001"), format="json")
            self._admin_client().post(
                "/records/",
                {
                    **self._record_payload(source_reference="record-002"),
                    "fleet_id": other_fleet_id,
                },
                format="json",
            )
            self._admin_client().post(
                "/records/",
                {
                    **self._record_payload(source_reference="record-003"),
                    "company_id": other_company_id,
                },
                format="json",
            )

        response = self._user_client().get(
            f"/records/?company_id={self.company_id}&fleet_id={self.fleet_id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["source_reference"], "record-001")

    def test_admin_can_crud_daily_snapshots(self) -> None:
        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            create_response = self._admin_client().post(
                "/daily-snapshots/",
                self._snapshot_payload(),
                format="json",
            )

        snapshot_id = create_response.data["daily_delivery_input_snapshot_id"]

        list_response = self._admin_client().get("/daily-snapshots/")
        detail_response = self._admin_client().get(f"/daily-snapshots/{snapshot_id}/")

        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            update_response = self._admin_client().patch(
                f"/daily-snapshots/{snapshot_id}/",
                {"delivery_count": 18},
                format="json",
            )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(update_response.status_code, 200)

    def test_daily_snapshot_list_supports_company_fleet_service_date_and_status_filters(self) -> None:
        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            self._admin_client().post("/daily-snapshots/", self._snapshot_payload(), format="json")
            self._admin_client().post(
                "/daily-snapshots/",
                {
                    **self._snapshot_payload(),
                    "driver_id": str(uuid4()),
                    "status": DailyDeliveryInputSnapshot.Status.SUPERSEDED,
                },
                format="json",
            )
            self._admin_client().post(
                "/daily-snapshots/",
                {
                    **self._snapshot_payload(),
                    "company_id": str(uuid4()),
                    "fleet_id": str(uuid4()),
                    "driver_id": str(uuid4()),
                    "service_date": "2026-03-25",
                },
                format="json",
            )

        response = self._user_client().get(
            "/daily-snapshots/",
            {
                "company_id": self.company_id,
                "fleet_id": self.fleet_id,
                "service_date": self.service_date,
                "status": DailyDeliveryInputSnapshot.Status.ACTIVE,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["company_id"], self.company_id)
        self.assertEqual(response.data[0]["fleet_id"], self.fleet_id)
        self.assertEqual(response.data[0]["service_date"], self.service_date)

    @patch(
        "deliveryrecords.services.source_clients.SourceClients.list_confirmed_dispatch_upload_rows",
        create=True,
    )
    @patch(
        "deliveryrecords.services.source_clients.SourceClients.bulk_lookup_attendance_days",
        create=True,
    )
    def test_bootstrap_from_dispatch_creates_daily_snapshots(self, mock_lookup_days, mock_list_rows) -> None:
        upload_row_id = str(uuid4())
        mock_list_rows.return_value = [
            {
                "upload_batch_id": str(uuid4()),
                "upload_row_id": upload_row_id,
                "external_user_name": "ZD홍길동",
                "small_region_text": "10H2",
                "detailed_region_text": "10H2-가",
                "box_count": 133,
                "household_count": 90,
                "matched_driver_id": self.driver_id,
            }
        ]
        mock_lookup_days.return_value = [
            {
                "driver_id": self.driver_id,
                "attendance_date": self.service_date,
                "final_status": "worked",
            }
        ]

        response = self._admin_client().post(
            "/daily-snapshots/bootstrap-from-dispatch/",
            {
                "company_id": self.company_id,
                "fleet_id": self.fleet_id,
                "service_date": self.service_date,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(response.data["skipped_count"], 0)
        self.assertEqual(len(response.data["created_snapshot_ids"]), 1)

        record = DeliveryRecord.objects.get(source_reference=f"dispatch-upload-row:{upload_row_id}")
        snapshot = DailyDeliveryInputSnapshot.objects.get(
            company_id=self.company_id,
            fleet_id=self.fleet_id,
            driver_id=self.driver_id,
            service_date=self.service_date,
        )

        self.assertEqual(record.delivery_count, 133)
        self.assertEqual(record.payload["household_count"], 90)
        self.assertEqual(record.payload["small_region_text"], "10H2")
        self.assertEqual(record.payload["detailed_region_text"], "10H2-가")
        self.assertEqual(snapshot.delivery_count, 133)
        self.assertEqual(snapshot.total_distance_km, Decimal("0.00"))
        self.assertEqual(snapshot.total_base_amount, Decimal("0.00"))
        self.assertEqual(snapshot.source_record_count, 1)

    @patch(
        "deliveryrecords.services.source_clients.SourceClients.list_confirmed_dispatch_upload_rows",
        create=True,
    )
    @patch(
        "deliveryrecords.services.source_clients.SourceClients.bulk_lookup_attendance_days",
        create=True,
    )
    def test_bootstrap_from_dispatch_aggregates_multiple_rows_for_same_driver(self, mock_lookup_days, mock_list_rows) -> None:
        upload_row_id_1 = str(uuid4())
        upload_row_id_2 = str(uuid4())
        mock_list_rows.return_value = [
            {
                "upload_batch_id": str(uuid4()),
                "upload_row_id": upload_row_id_1,
                "external_user_name": "ZD홍길동",
                "small_region_text": "10H2",
                "detailed_region_text": "10H2-가",
                "box_count": 100,
                "household_count": 50,
                "matched_driver_id": self.driver_id,
            },
            {
                "upload_batch_id": str(uuid4()),
                "upload_row_id": upload_row_id_2,
                "external_user_name": "ZD홍길동",
                "small_region_text": "10H3",
                "detailed_region_text": "10H3-나",
                "box_count": 33,
                "household_count": 20,
                "matched_driver_id": self.driver_id,
            },
        ]
        mock_lookup_days.return_value = [
            {
                "driver_id": self.driver_id,
                "attendance_date": self.service_date,
                "final_status": "worked",
            }
        ]

        response = self._admin_client().post(
            "/daily-snapshots/bootstrap-from-dispatch/",
            {
                "company_id": self.company_id,
                "fleet_id": self.fleet_id,
                "service_date": self.service_date,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(response.data["skipped_count"], 0)

        records = DeliveryRecord.objects.filter(
            source_reference__in=[
                f"dispatch-upload-row:{upload_row_id_1}",
                f"dispatch-upload-row:{upload_row_id_2}",
            ]
        ).order_by("source_reference")
        snapshot = DailyDeliveryInputSnapshot.objects.get(
            company_id=self.company_id,
            fleet_id=self.fleet_id,
            driver_id=self.driver_id,
            service_date=self.service_date,
        )

        self.assertEqual(records.count(), 2)
        self.assertEqual(records[0].delivery_count + records[1].delivery_count, 133)
        self.assertEqual(
            {records[0].payload["small_region_text"], records[1].payload["small_region_text"]},
            {"10H2", "10H3"},
        )
        self.assertEqual(snapshot.delivery_count, 133)
        self.assertEqual(snapshot.source_record_count, 2)

    @patch(
        "deliveryrecords.services.source_clients.SourceClients.list_confirmed_dispatch_upload_rows",
        create=True,
    )
    @patch(
        "deliveryrecords.services.source_clients.SourceClients.bulk_lookup_attendance_days",
        create=True,
    )
    def test_bootstrap_from_dispatch_skips_existing_active_snapshot(self, mock_lookup_days, mock_list_rows) -> None:
        mock_list_rows.return_value = [
            {
                "upload_batch_id": str(uuid4()),
                "upload_row_id": str(uuid4()),
                "external_user_name": "ZD홍길동",
                "small_region_text": "10H2",
                "detailed_region_text": "10H2-가",
                "box_count": 133,
                "household_count": 90,
                "matched_driver_id": self.driver_id,
            }
        ]
        mock_lookup_days.return_value = [
            {
                "driver_id": self.driver_id,
                "attendance_date": self.service_date,
                "final_status": "worked",
            }
        ]
        DailyDeliveryInputSnapshot.objects.create(
            company_id=self.company_id,
            fleet_id=self.fleet_id,
            driver_id=self.driver_id,
            service_date=self.service_date,
            delivery_count=20,
            total_distance_km=Decimal("0.00"),
            total_base_amount=Decimal("0.00"),
            source_record_count=1,
            status=DailyDeliveryInputSnapshot.Status.ACTIVE,
        )

        response = self._admin_client().post(
            "/daily-snapshots/bootstrap-from-dispatch/",
            {
                "company_id": self.company_id,
                "fleet_id": self.fleet_id,
                "service_date": self.service_date,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created_count"], 0)
        self.assertEqual(response.data["skipped_count"], 1)

    @patch(
        "deliveryrecords.services.source_clients.SourceClients.list_confirmed_dispatch_upload_rows",
        create=True,
    )
    @patch(
        "deliveryrecords.services.source_clients.SourceClients.bulk_lookup_attendance_days",
        create=True,
    )
    def test_bootstrap_from_dispatch_skips_non_worked_attendance_days(self, mock_lookup_days, mock_list_rows) -> None:
        day_off_driver_id = str(uuid4())
        mock_list_rows.return_value = [
            {
                "upload_batch_id": str(uuid4()),
                "upload_row_id": str(uuid4()),
                "external_user_name": "ZD홍길동",
                "small_region_text": "10H2",
                "detailed_region_text": "10H2-가",
                "box_count": 133,
                "household_count": 90,
                "matched_driver_id": self.driver_id,
            },
            {
                "upload_batch_id": str(uuid4()),
                "upload_row_id": str(uuid4()),
                "external_user_name": "ZD휴무",
                "small_region_text": "00",
                "detailed_region_text": "",
                "box_count": 0,
                "household_count": 0,
                "matched_driver_id": day_off_driver_id,
            },
        ]
        mock_lookup_days.return_value = [
            {
                "driver_id": self.driver_id,
                "attendance_date": self.service_date,
                "final_status": "worked",
            },
            {
                "driver_id": day_off_driver_id,
                "attendance_date": self.service_date,
                "final_status": "day_off",
            },
        ]

        response = self._admin_client().post(
            "/daily-snapshots/bootstrap-from-dispatch/",
            {
                "company_id": self.company_id,
                "fleet_id": self.fleet_id,
                "service_date": self.service_date,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(response.data["skipped_count"], 1)
        self.assertTrue(
            DailyDeliveryInputSnapshot.objects.filter(
                company_id=self.company_id,
                fleet_id=self.fleet_id,
                driver_id=self.driver_id,
                service_date=self.service_date,
            ).exists()
        )
        self.assertFalse(
            DailyDeliveryInputSnapshot.objects.filter(
                company_id=self.company_id,
                fleet_id=self.fleet_id,
                driver_id=day_off_driver_id,
                service_date=self.service_date,
            ).exists()
        )

    @patch(
        "deliveryrecords.services.source_clients.SourceClients.list_confirmed_dispatch_upload_rows",
        create=True,
    )
    @patch(
        "deliveryrecords.services.source_clients.SourceClients.bulk_lookup_attendance_days",
        create=True,
    )
    def test_bootstrap_from_dispatch_rejects_missing_attendance_truth(self, mock_lookup_days, mock_list_rows) -> None:
        mock_list_rows.return_value = [
            {
                "upload_batch_id": str(uuid4()),
                "upload_row_id": str(uuid4()),
                "external_user_name": "ZD홍길동",
                "small_region_text": "10H2",
                "detailed_region_text": "10H2-가",
                "box_count": 133,
                "household_count": 90,
                "matched_driver_id": self.driver_id,
            }
        ]
        mock_lookup_days.return_value = []

        response = self._admin_client().post(
            "/daily-snapshots/bootstrap-from-dispatch/",
            {
                "company_id": self.company_id,
                "fleet_id": self.fleet_id,
                "service_date": self.service_date,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertEqual(DailyDeliveryInputSnapshot.objects.count(), 0)

    def test_put_and_delete_are_not_allowed_for_detail_routes(self) -> None:
        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            record_response = self._admin_client().post("/records/", self._record_payload(), format="json")
            snapshot_response = self._admin_client().post(
                "/daily-snapshots/",
                self._snapshot_payload(),
                format="json",
            )

        record_id = record_response.data["delivery_record_id"]
        snapshot_id = snapshot_response.data["daily_delivery_input_snapshot_id"]

        responses = (
            self._admin_client().put(f"/records/{record_id}/", self._record_payload(), format="json"),
            self._admin_client().delete(f"/records/{record_id}/"),
            self._admin_client().put(f"/daily-snapshots/{snapshot_id}/", self._snapshot_payload(), format="json"),
            self._admin_client().delete(f"/daily-snapshots/{snapshot_id}/"),
        )

        self.assertTrue(all(response.status_code == 405 for response in responses))

    def test_create_is_rejected_when_company_fleet_or_driver_is_missing(self) -> None:
        missing_cases = (
            (
                "company_id",
                [HTTPError("http://organization-master-api:8000/companies/missing/", 404, "Not Found", None, None)],
            ),
            (
                "fleet_id",
                [
                    self._build_json_response(
                        f'{{"company_id":"{self.company_id}","name":"Seed Company"}}'
                    ),
                    HTTPError("http://organization-master-api:8000/fleets/missing/", 404, "Not Found", None, None),
                ],
            ),
            (
                "driver_id",
                [
                    self._build_json_response(
                        f'{{"company_id":"{self.company_id}","name":"Seed Company"}}'
                    ),
                    self._build_json_response(
                        f'{{"fleet_id":"{self.fleet_id}","company_id":"{self.company_id}","name":"Seed Fleet"}}'
                    ),
                    HTTPError("http://driver-profile-api:8000/drivers/missing/", 404, "Not Found", None, None),
                ],
            ),
        )

        expected_contracts = {
            "company_id": ("company_id", "Referenced company does not exist."),
            "fleet_id": ("fleet_id", "Referenced fleet does not exist."),
            "driver_id": ("driver_id", "Referenced driver does not exist."),
        }

        for field, side_effect in missing_cases:
            with self.subTest(field=field), patch(
                "deliveryrecords.services.source_clients.urlopen",
                side_effect=side_effect,
            ):
                response = self._admin_client().post("/records/", self._record_payload(), format="json")

            self.assertEqual(response.status_code, 400)
            expected_field, expected_message = expected_contracts[field]
            self.assertEqual(response.data["code"], "validation_error")
            self.assertEqual(response.data["details"][expected_field][0], expected_message)

    def test_patch_validates_source_scope_changes(self) -> None:
        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            create_response = self._admin_client().post("/records/", self._record_payload(), format="json")

        record_id = create_response.data["delivery_record_id"]
        missing_company_id = str(uuid4())

        with patch(
            "deliveryrecords.services.source_clients.urlopen",
            side_effect=[HTTPError(f"http://organization-master-api:8000/companies/{missing_company_id}/", 404, "Not Found", None, None)],
        ):
            response = self._admin_client().patch(
                f"/records/{record_id}/",
                {"company_id": missing_company_id},
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertEqual(response.data["details"]["company_id"][0], "Referenced company does not exist.")

    def test_duplicate_active_snapshot_is_rejected(self) -> None:
        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            first_response = self._admin_client().post(
                "/daily-snapshots/",
                self._snapshot_payload(),
                format="json",
            )
        self.assertEqual(first_response.status_code, 201)

        with patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_company_fleet_scope",
            return_value=None,
        ), patch(
            "deliveryrecords.services.source_clients.SourceClients.validate_driver_exists",
            return_value=None,
        ):
            second_response = self._admin_client().post(
                "/daily-snapshots/",
                self._snapshot_payload(),
                format="json",
            )

        self.assertEqual(second_response.status_code, 400)
