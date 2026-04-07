from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class DeliveryRecord(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "draft"
        CONFIRMED = "confirmed", "confirmed"
        VOID = "void", "void"

    delivery_record_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    fleet_id = models.UUIDField()
    driver_id = models.UUIDField()
    service_date = models.DateField()
    source_reference = models.CharField(max_length=128)
    delivery_count = models.PositiveIntegerField()
    distance_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    base_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    status = models.CharField(max_length=32, choices=Status.choices)
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ("service_date", "delivery_record_id")
        constraints = [
            models.UniqueConstraint(
                fields=("company_id", "fleet_id", "driver_id", "service_date", "source_reference"),
                name="unique_delivery_record_source_reference_per_scope_and_date",
            )
        ]


class DailyDeliveryInputSnapshot(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "active"
        SUPERSEDED = "superseded", "superseded"

    daily_delivery_input_snapshot_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    company_id = models.UUIDField()
    fleet_id = models.UUIDField()
    driver_id = models.UUIDField()
    service_date = models.DateField()
    delivery_count = models.PositiveIntegerField()
    total_distance_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    total_base_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    source_record_count = models.PositiveIntegerField()
    status = models.CharField(max_length=32, choices=Status.choices)

    class Meta:
        ordering = ("service_date", "daily_delivery_input_snapshot_id")
        constraints = [
            models.UniqueConstraint(
                fields=("company_id", "fleet_id", "driver_id", "service_date"),
                condition=Q(status="active"),
                name="unique_active_daily_delivery_input_snapshot_per_scope_and_date",
            )
        ]

    def clean(self):
        super().clean()

        if self.status != self.Status.ACTIVE:
            return

        if not all((self.company_id, self.fleet_id, self.driver_id, self.service_date)):
            return

        active_exists = (
            DailyDeliveryInputSnapshot.objects.filter(
                company_id=self.company_id,
                fleet_id=self.fleet_id,
                driver_id=self.driver_id,
                service_date=self.service_date,
                status=self.Status.ACTIVE,
            )
            .exclude(pk=self.pk)
            .exists()
        )

        if active_exists:
            raise ValidationError(
                {
                    "status": (
                        "An active daily delivery input snapshot already exists for this "
                        "company, fleet, driver, and service date."
                    )
                }
            )
