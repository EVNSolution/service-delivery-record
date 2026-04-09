from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from deliveryrecords.exceptions import ServiceUnavailableError
from deliveryrecords.models import DailyDeliveryInputSnapshot, DeliveryRecord
from deliveryrecords.services.source_clients import SourceClients, SourceServiceError, SourceValidationError


class _SourceValidatedModelSerializer(serializers.ModelSerializer):
    source_clients_class = SourceClients

    def _get_authorization(self) -> str:
        request = self.context.get("request")
        if request is None:
            return ""
        return request.headers.get("Authorization", "")

    def _apply_attrs(self, candidate, attrs):
        for field, value in attrs.items():
            setattr(candidate, field, value)
        return candidate

    def _validate_model(self, candidate) -> None:
        try:
            candidate.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(getattr(exc, "message_dict", exc.messages)) from exc

    def _validate_sources(self, candidate) -> None:
        authorization = self._get_authorization()
        clients = self.source_clients_class()
        try:
            clients.validate_company_fleet_scope(
                company_id=str(candidate.company_id),
                fleet_id=str(candidate.fleet_id),
                authorization=authorization,
            )
            clients.validate_driver_exists(
                driver_id=str(candidate.driver_id),
                authorization=authorization,
            )
        except SourceValidationError as exc:
            raise serializers.ValidationError({exc.field: [exc.message]}) from exc
        except SourceServiceError as exc:
            raise ServiceUnavailableError(str(exc)) from exc


class DeliveryRecordSerializer(_SourceValidatedModelSerializer):
    class Meta:
        model = DeliveryRecord
        fields = (
            "delivery_record_id",
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
        )
        read_only_fields = ("delivery_record_id",)

    def validate(self, attrs):
        candidate = self._apply_attrs(self.instance or DeliveryRecord(), attrs)
        self._validate_sources(candidate)
        self._validate_model(candidate)
        return attrs


class DailyDeliveryInputSnapshotSerializer(_SourceValidatedModelSerializer):
    class Meta:
        model = DailyDeliveryInputSnapshot
        fields = (
            "daily_delivery_input_snapshot_id",
            "company_id",
            "fleet_id",
            "driver_id",
            "service_date",
            "delivery_count",
            "total_distance_km",
            "total_base_amount",
            "source_record_count",
            "status",
        )
        read_only_fields = ("daily_delivery_input_snapshot_id",)

    def validate(self, attrs):
        candidate = self._apply_attrs(self.instance or DailyDeliveryInputSnapshot(), attrs)
        self._validate_sources(candidate)
        self._validate_model(candidate)
        return attrs


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()


class DispatchSnapshotBootstrapRequestSerializer(serializers.Serializer):
    company_id = serializers.UUIDField()
    fleet_id = serializers.UUIDField()
    service_date = serializers.DateField()


class DispatchSnapshotBootstrapResultSerializer(serializers.Serializer):
    created_count = serializers.IntegerField(min_value=0)
    skipped_count = serializers.IntegerField(min_value=0)
    created_snapshot_ids = serializers.ListField(child=serializers.UUIDField())
