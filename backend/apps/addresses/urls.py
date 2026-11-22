"""URL routes for addresses."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.addresses.views import (
    AddressViewSet,
    MyAddressCreateView,
    MyAddressListView,
)

app_name = "addresses"

router = SimpleRouter(trailing_slash=True)
router.register("", AddressViewSet, basename="address")

urlpatterns = [
    path("mine/", MyAddressListView.as_view(), name="my-addresses"),
    path("mine/add/", MyAddressCreateView.as_view(), name="my-address-add"),
    *router.urls,
]
