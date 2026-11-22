"""URL routes for orders."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.orders.views import (
    GuestCheckoutView,
    GuestOrderLookupView,
    CheckoutPreviewView,
    CheckoutView,
    MyOrdersView,
    OrderViewSet,
)

app_name = "orders"

router = SimpleRouter(trailing_slash=True)
router.register("", OrderViewSet, basename="order")

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("checkout/preview/", CheckoutPreviewView.as_view(), name="checkout-preview"),
    # Round 25: the customer storefront has no login, so checkout and order
    # lookup are public. Admin order management stays behind authentication.
    path("checkout/guest/", GuestCheckoutView.as_view(), name="guest-checkout"),
    path("lookup/", GuestOrderLookupView.as_view(), name="guest-order-lookup"),
    path("mine/", MyOrdersView.as_view(), name="my-orders"),
    *router.urls,
]
