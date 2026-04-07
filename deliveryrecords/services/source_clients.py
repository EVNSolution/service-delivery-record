import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class SourceClientError(Exception):
    pass


@dataclass
class SourceValidationError(SourceClientError):
    field: str
    message: str

    def __str__(self) -> str:
        return self.message


class SourceServiceError(SourceClientError):
    pass


class SourceClients:
    def _build_url(self, base_url: str, path: str) -> str:
        return f"{base_url.rstrip('/')}{path}"

    def _request_json(self, *, url: str, authorization: str):
        headers = {"Accept": "application/json"}
        if authorization:
            headers["Authorization"] = authorization

        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise SourceValidationError(field="", message="Not found.") from exc
            raise SourceServiceError(f"Upstream request failed: {url}") from exc
        except (URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceServiceError(f"Upstream request failed: {url}") from exc

        if not isinstance(payload, dict):
            raise SourceServiceError(f"Upstream request failed: {url}")

        return payload

    def _request_or_validation_error(
        self,
        *,
        url: str,
        authorization: str,
        field: str,
        message: str,
    ):
        try:
            return self._request_json(url=url, authorization=authorization)
        except SourceValidationError as exc:
            if exc.field:
                raise
            raise SourceValidationError(field=field, message=message) from exc

    def validate_company_fleet_scope(self, *, company_id: str, fleet_id: str, authorization: str) -> None:
        company_payload = self._request_or_validation_error(
            url=self._build_url(settings.ORGANIZATION_MASTER_BASE_URL, f"/companies/{company_id}/"),
            authorization=authorization,
            field="company_id",
            message="Referenced company does not exist.",
        )
        fleet_payload = self._request_or_validation_error(
            url=self._build_url(settings.ORGANIZATION_MASTER_BASE_URL, f"/fleets/{fleet_id}/"),
            authorization=authorization,
            field="fleet_id",
            message="Referenced fleet does not exist.",
        )

        if str(company_payload.get("company_id")) != company_id:
            raise SourceServiceError("Upstream request failed: malformed company payload.")
        if str(fleet_payload.get("fleet_id")) != fleet_id:
            raise SourceServiceError("Upstream request failed: malformed fleet payload.")
        if str(fleet_payload.get("company_id")) != company_id:
            raise SourceValidationError(
                field="fleet_id",
                message="Referenced fleet does not belong to the referenced company.",
            )

    def validate_driver_exists(self, *, driver_id: str, authorization: str) -> None:
        driver_payload = self._request_or_validation_error(
            url=self._build_url(settings.DRIVER_PROFILE_BASE_URL, f"/{driver_id}/"),
            authorization=authorization,
            field="driver_id",
            message="Referenced driver does not exist.",
        )

        if str(driver_payload.get("driver_id")) != driver_id:
            raise SourceServiceError("Upstream request failed: malformed driver payload.")
