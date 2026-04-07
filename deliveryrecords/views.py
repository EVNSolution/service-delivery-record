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

from deliveryrecords.models import DailyDeliveryInputSnapshot, DeliveryRecord
from deliveryrecords.permissions import AuthenticatedReadAdminWrite
from deliveryrecords.serializers import (
    DailyDeliveryInputSnapshotSerializer,
    DeliveryRecordSerializer,
    HealthSerializer,
)


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
        queryset = super().get_queryset()
        driver_id = self.request.query_params.get("driver_id")
        status = self.request.query_params.get("status")

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
