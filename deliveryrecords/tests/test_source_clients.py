from unittest import TestCase
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from django.test import override_settings


class SourceClientsTests(TestCase):
    def setUp(self) -> None:
        self.authorization = "Bearer token"
        self.company_id = "30000000-0000-0000-0000-000000000001"
        self.fleet_id = "40000000-0000-0000-0000-000000000001"
        self.driver_id = "50000000-0000-0000-0000-000000000001"

    def _build_response(self, payload: str):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = payload.encode("utf-8")
        return response

    @override_settings(
        ORGANIZATION_MASTER_BASE_URL="http://organization-master-api:8000",
        DRIVER_PROFILE_BASE_URL="http://driver-profile-api:8000",
    )
    @patch("deliveryrecords.services.source_clients.urlopen")
    def test_validate_company_fleet_scope_forwards_caller_token_to_upstream_calls(self, mocked_urlopen):
        from deliveryrecords.services.source_clients import SourceClients

        mocked_urlopen.side_effect = [
            self._build_response(
                f'{{"company_id":"{self.company_id}","name":"Seed Company"}}'
            ),
            self._build_response(
                f'{{"fleet_id":"{self.fleet_id}","company_id":"{self.company_id}","name":"Seed Fleet"}}'
            ),
        ]

        SourceClients().validate_company_fleet_scope(
            company_id=self.company_id,
            fleet_id=self.fleet_id,
            authorization=self.authorization,
        )

        self.assertEqual(
            [call.args[0].get_header("Authorization") for call in mocked_urlopen.call_args_list],
            [self.authorization, self.authorization],
        )

    @override_settings(ORGANIZATION_MASTER_BASE_URL="http://organization-master-api:8000")
    @patch("deliveryrecords.services.source_clients.urlopen")
    def test_validate_company_fleet_scope_rejects_unknown_company(self, mocked_urlopen):
        from deliveryrecords.services.source_clients import SourceClients, SourceValidationError

        mocked_urlopen.side_effect = HTTPError(
            url="http://organization-master-api:8000/companies/missing/",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

        with self.assertRaises(SourceValidationError) as context:
            SourceClients().validate_company_fleet_scope(
                company_id="30000000-0000-0000-0000-000000000099",
                fleet_id=self.fleet_id,
                authorization=self.authorization,
            )

        self.assertEqual(context.exception.field, "company_id")

    @override_settings(ORGANIZATION_MASTER_BASE_URL="http://organization-master-api:8000")
    @patch("deliveryrecords.services.source_clients.urlopen")
    def test_validate_company_fleet_scope_rejects_mismatched_fleet_membership(self, mocked_urlopen):
        from deliveryrecords.services.source_clients import SourceClients, SourceValidationError

        mocked_urlopen.side_effect = [
            self._build_response(
                f'{{"company_id":"{self.company_id}","name":"Seed Company"}}'
            ),
            self._build_response(
                f'{{"fleet_id":"{self.fleet_id}","company_id":"30000000-0000-0000-0000-000000000099","name":"Seed Fleet"}}'
            ),
        ]

        with self.assertRaises(SourceValidationError) as context:
            SourceClients().validate_company_fleet_scope(
                company_id=self.company_id,
                fleet_id=self.fleet_id,
                authorization=self.authorization,
            )

        self.assertEqual(context.exception.field, "fleet_id")

    @override_settings(ORGANIZATION_MASTER_BASE_URL="http://organization-master-api:8000")
    @patch("deliveryrecords.services.source_clients.urlopen")
    def test_validate_company_fleet_scope_rejects_unknown_fleet(self, mocked_urlopen):
        from deliveryrecords.services.source_clients import SourceClients, SourceValidationError

        mocked_urlopen.side_effect = [
            self._build_response(
                f'{{"company_id":"{self.company_id}","name":"Seed Company"}}'
            ),
            HTTPError(
                url="http://organization-master-api:8000/fleets/missing/",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            ),
        ]

        with self.assertRaises(SourceValidationError) as context:
            SourceClients().validate_company_fleet_scope(
                company_id=self.company_id,
                fleet_id="40000000-0000-0000-0000-000000000099",
                authorization=self.authorization,
            )

        self.assertEqual(context.exception.field, "fleet_id")

    @override_settings(DRIVER_PROFILE_BASE_URL="http://driver-profile-api:8000")
    @patch("deliveryrecords.services.source_clients.urlopen")
    def test_validate_driver_exists_forwards_caller_token_and_rejects_missing_driver(self, mocked_urlopen):
        from deliveryrecords.services.source_clients import SourceClients, SourceValidationError

        mocked_urlopen.side_effect = [
            self._build_response(
                f'{{"driver_id":"{self.driver_id}","company_id":"{self.company_id}","fleet_id":"{self.fleet_id}"}}'
            ),
            HTTPError(
                url=f"http://driver-profile-api:8000/drivers/{self.driver_id}/",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            ),
        ]

        SourceClients().validate_driver_exists(
            driver_id=self.driver_id,
            authorization=self.authorization,
        )

        self.assertEqual(mocked_urlopen.call_args_list[0].args[0].get_header("Authorization"), self.authorization)
        self.assertEqual(
            mocked_urlopen.call_args_list[0].args[0].full_url,
            f"http://driver-profile-api:8000/{self.driver_id}/",
        )

        with self.assertRaises(SourceValidationError) as context:
            SourceClients().validate_driver_exists(
                driver_id="50000000-0000-0000-0000-000000000099",
                authorization=self.authorization,
            )

        self.assertEqual(context.exception.field, "driver_id")
