from django.urls import include, path
from rest_framework.routers import SimpleRouter

from deliveryrecords.views import (
    DailyDeliveryInputSnapshotViewSet,
    DeliveryRecordViewSet,
    DispatchSnapshotBootstrapView,
    HealthView,
)

router = SimpleRouter()
router.register("records", DeliveryRecordViewSet, basename="delivery-record")
router.register("daily-snapshots", DailyDeliveryInputSnapshotViewSet, basename="daily-delivery-snapshot")

urlpatterns = [
    path("daily-snapshots/bootstrap-from-dispatch/", DispatchSnapshotBootstrapView.as_view()),
    path("", include(router.urls)),
    path("health/", HealthView.as_view(), name="health"),
]
