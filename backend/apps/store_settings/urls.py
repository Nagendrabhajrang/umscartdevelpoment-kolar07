"""URL routes for store settings."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.store_settings.views import (
    DeliveryQuoteView,
    GenerateUpiQrView,
    DeliverySlabViewSet,
    StoreHolidayViewSet,
    StoreSettingsView,
)

app_name = "store_settings"

router = SimpleRouter(trailing_slash=True)
router.register("delivery-slabs", DeliverySlabViewSet, basename="delivery-slab")
router.register("holidays", StoreHolidayViewSet, basename="holiday")

urlpatterns = [
    path("", StoreSettingsView.as_view(), name="store-settings"),
    path("delivery-quote/", DeliveryQuoteView.as_view(), name="delivery-quote"),
    path("upi-qr/", GenerateUpiQrView.as_view(), name="generate-upi-qr"),
    *router.urls,
]
