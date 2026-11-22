"""URL routes for the wishlist app."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.wishlist.views import (
    MyWishlistView,
    WishlistItemViewSet,
    WishlistToggleView,
    WishlistViewSet,
)

app_name = "wishlist"

router = SimpleRouter(trailing_slash=True)
router.register("lists", WishlistViewSet, basename="wishlist")
router.register("items", WishlistItemViewSet, basename="wishlist-item")

urlpatterns = [
    path("", MyWishlistView.as_view(), name="my-wishlist"),
    path("toggle/", WishlistToggleView.as_view(), name="wishlist-toggle"),
    *router.urls,
]
