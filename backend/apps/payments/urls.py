"""URL routes for payments."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.payments.views import (
    OrderPaymentView,
    PaymentVerificationViewSet,
    PaymentViewSet,
    RefundViewSet,
)

app_name = "payments"

router = SimpleRouter(trailing_slash=True)
router.register("refunds", RefundViewSet, basename="refund")
router.register("verifications", PaymentVerificationViewSet, basename="verification")
router.register("", PaymentViewSet, basename="payment")

urlpatterns = [
    path("order/<int:order_id>/", OrderPaymentView.as_view(), name="order-payment"),
    *router.urls,
]
