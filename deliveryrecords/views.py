from decimal import Decimal
try:
    from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
except ModuleNotFoundError:
    class OpenApiParameter:  # pragma: no cover - docs fallback only
        QUERY = "query"

        def __init__(self, *args, **kwargs):
            pass

    def extend_schema(*args, **kwargs):
        def decorator(target):
            return target

        return decorator

    def extend_schema_view(**kwargs):
        def decorator(target):
            return target

        return decorator

from uuid import UUID

from rest_framework import permissions
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction

from deliveryrecords.models import DailyDeliveryInputSnapshot, DeliveryRecord
from deliveryrecords.permissions_navigation import require_nav_access
from deliveryrecords.permissions import AuthenticatedReadAdminWrite
from deliveryrecords.serializers import (
    DailyDeliveryInputSnapshotSerializer,
    DispatchSnapshotBootstrapRequestSerializer,
    DispatchSnapshotBootstrapResultSerializer,
    DeliveryRecordSerializer,
    HealthSerializer,
)
from deliveryrecords.services.source_clients import SourceClients, SourceServiceError


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: HealthSerializer})
    def get(self, request):
        return Response({"status": "ok"})


def _parse_uuid_filter(value: str, *, field_name: str):
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValidationError({field_name: ["Must be a valid UUID."]}) from exc


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("driver_id", str, OpenApiParameter.QUERY),
            OpenApiParameter("company_id", str, OpenApiParameter.QUERY),
            OpenApiParameter("fleet_id", str, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
        ]
    )
)
class DeliveryRecordViewSet(viewsets.ModelViewSet):
    queryset = DeliveryRecord.objects.all()
    serializer_class = DeliveryRecordSerializer
    lookup_field = "delivery_record_id"
    permission_classes = [AuthenticatedReadAdminWrite]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if self.request.method == "GET":
            require_nav_access(self.request, "dispatch", "settlements")
        queryset = super().get_queryset()
        company_id = self.request.query_params.get("company_id")
        fleet_id = self.request.query_params.get("fleet_id")
        driver_id = self.request.query_params.get("driver_id")
        status = self.request.query_params.get("status")

        if company_id:
            queryset = queryset.filter(company_id=_parse_uuid_filter(company_id, field_name="company_id"))
        if fleet_id:
            queryset = queryset.filter(fleet_id=_parse_uuid_filter(fleet_id, field_name="fleet_id"))
        if driver_id:
            queryset = queryset.filter(driver_id=_parse_uuid_filter(driver_id, field_name="driver_id"))
        if status:
            valid_statuses = {choice for choice, _ in DeliveryRecord.Status.choices}
            if status not in valid_statuses:
                raise ValidationError({"status": [f"Must be one of: {', '.join(sorted(valid_statuses))}."]})
            queryset = queryset.filter(status=status)

        return queryset


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("driver_id", str, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
        ]
    )
)
class DailyDeliveryInputSnapshotViewSet(viewsets.ModelViewSet):
    queryset = DailyDeliveryInputSnapshot.objects.all()
    serializer_class = DailyDeliveryInputSnapshotSerializer
    lookup_field = "daily_delivery_input_snapshot_id"
    permission_classes = [AuthenticatedReadAdminWrite]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if self.request.method == "GET":
            require_nav_access(self.request, "dispatch", "settlements")
        queryset = super().get_queryset()
        company_id = self.request.query_params.get("company_id")
        fleet_id = self.request.query_params.get("fleet_id")
        service_date = self.request.query_params.get("service_date")
        driver_id = self.request.query_params.get("driver_id")
        status = self.request.query_params.get("status")

        if company_id:
            queryset = queryset.filter(company_id=_parse_uuid_filter(company_id, field_name="company_id"))
        if fleet_id:
            queryset = queryset.filter(fleet_id=_parse_uuid_filter(fleet_id, field_name="fleet_id"))
        if service_date:
            queryset = queryset.filter(service_date=service_date)
        if driver_id:
            queryset = queryset.filter(driver_id=_parse_uuid_filter(driver_id, field_name="driver_id"))
        if status:
            valid_statuses = {choice for choice, _ in DailyDeliveryInputSnapshot.Status.choices}
            if status not in valid_statuses:
                raise ValidationError({"status": [f"Must be one of: {', '.join(sorted(valid_statuses))}."]})
            queryset = queryset.filter(status=status)

        return queryset


class DispatchSnapshotBootstrapView(APIView):
    permission_classes = [AuthenticatedReadAdminWrite]

    @extend_schema(
        request=DispatchSnapshotBootstrapRequestSerializer,
        responses={200: DispatchSnapshotBootstrapResultSerializer},
    )
    def post(self, request):
        require_nav_access(request, "dispatch", "settlements")
        serializer = DispatchSnapshotBootstrapRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        authorization = request.headers.get("Authorization", "")

        try:
            upload_rows = SourceClients().list_confirmed_dispatch_upload_rows(
                company_id=str(payload["company_id"]),
                fleet_id=str(payload["fleet_id"]),
                service_date=str(payload["service_date"]),
                authorization=authorization,
            )
        except SourceServiceError as exc:
            raise ValidationError({"detail": [str(exc)]}) from exc

        created_snapshot_ids: list[str] = []
        skipped_count = 0
        rows_by_driver: dict[str, list[dict]] = {}
        for row in upload_rows:
            matched_driver_id = row.get("matched_driver_id")
            if not matched_driver_id:
                skipped_count += 1
                continue
            rows_by_driver.setdefault(str(matched_driver_id), []).append(row)

        attendance_days = SourceClients().bulk_lookup_attendance_days(
            keys=[
                {
                    "driver_id": driver_id,
                    "attendance_date": str(payload["service_date"]),
                }
                for driver_id in rows_by_driver
            ],
            authorization=authorization,
        )
        attendance_by_driver = {
            str(day.get("driver_id")): day
            for day in attendance_days
            if isinstance(day, dict) and str(day.get("attendance_date")) == str(payload["service_date"])
        }

        with transaction.atomic():
            for driver_id, driver_rows in rows_by_driver.items():
                attendance_day = attendance_by_driver.get(driver_id)
                if attendance_day is None:
                    raise ValidationError({"detail": ["Attendance truth is required before bootstrap."]})
                if attendance_day.get("final_status") != "worked":
                    skipped_count += 1
                    continue

                existing_snapshot = DailyDeliveryInputSnapshot.objects.filter(
                    company_id=payload["company_id"],
                    fleet_id=payload["fleet_id"],
                    driver_id=driver_id,
                    service_date=payload["service_date"],
                    status=DailyDeliveryInputSnapshot.Status.ACTIVE,
                ).first()
                if existing_snapshot is not None:
                    skipped_count += 1
                    continue

                delivery_count = 0
                source_record_count = 0
                for row in driver_rows:
                    upload_row_id = str(row.get("upload_row_id", ""))
                    source_reference = f"dispatch-upload-row:{upload_row_id}"
                    record, _ = DeliveryRecord.objects.get_or_create(
                        company_id=payload["company_id"],
                        fleet_id=payload["fleet_id"],
                        driver_id=driver_id,
                        service_date=payload["service_date"],
                        source_reference=source_reference,
                        defaults={
                            "delivery_count": int(row.get("box_count", 0)),
                            "distance_km": Decimal("0.00"),
                            "base_amount": Decimal("0.00"),
                            "status": DeliveryRecord.Status.CONFIRMED,
                            "payload": {
                                "upload_batch_id": row.get("upload_batch_id"),
                                "upload_row_id": row.get("upload_row_id"),
                                "external_user_name": row.get("external_user_name", ""),
                                "small_region_text": row.get("small_region_text", ""),
                                "detailed_region_text": row.get("detailed_region_text", ""),
                                "household_count": int(row.get("household_count", 0)),
                            },
                        },
                    )
                    delivery_count += record.delivery_count
                    source_record_count += 1

                snapshot = DailyDeliveryInputSnapshot.objects.create(
                    company_id=payload["company_id"],
                    fleet_id=payload["fleet_id"],
                    driver_id=driver_id,
                    service_date=payload["service_date"],
                    delivery_count=delivery_count,
                    total_distance_km=Decimal("0.00"),
                    total_base_amount=Decimal("0.00"),
                    source_record_count=source_record_count,
                    status=DailyDeliveryInputSnapshot.Status.ACTIVE,
                )
                created_snapshot_ids.append(str(snapshot.daily_delivery_input_snapshot_id))

        return Response(
            {
                "created_count": len(created_snapshot_ids),
                "skipped_count": skipped_count,
                "created_snapshot_ids": created_snapshot_ids,
            }
        )
