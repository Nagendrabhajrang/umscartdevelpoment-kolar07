"""URL routes for the cart app.

Customer-facing routes are hand-written paths (they operate on "my cart");
administrative cart listings live on the router.
"""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.cart.views import (
    CartCouponView,
    CartItemCollectionView,
    CartItemDecrementView,
    CartItemDetailView,
    CartItemIncrementView,
    CartMergeView,
    CartSummaryView,
    CartViewSet,
    MyCartView,
)

app_name = "cart"

router = SimpleRouter(trailing_slash=True)
router.register("carts", CartViewSet, basename="cart")

urlpatterns = [
    path("", MyCartView.as_view(), name="my-cart"),
    path("items/", CartItemCollectionView.as_view(), name="cart-items"),
    path("items/<int:item_id>/", CartItemDetailView.as_view(), name="cart-item-detail"),
    path("items/<int:item_id>/increment/", CartItemIncrementView.as_view(),
         name="cart-item-increment"),
    path("items/<int:item_id>/decrement/", CartItemDecrementView.as_view(),
         name="cart-item-decrement"),
    path("summary/", CartSummaryView.as_view(), name="cart-summary"),
    path("coupon/", CartCouponView.as_view(), name="cart-coupon"),
    path("merge/", CartMergeView.as_view(), name="cart-merge"),
    *router.urls,
]
