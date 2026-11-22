"""Wishlist API views.

SECURITY NOTE: authentication is not implemented in this phase. These
endpoints are unrestricted and must NOT be exposed publicly until the
authentication layer ships.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.services import get_product_or_404
from apps.wishlist import selectors, services
from apps.wishlist.serializers import (
    AddWishlistItemSerializer,
    MoveToCartSerializer,
    ToggleWishlistItemSerializer,
    WishlistItemSerializer,
    WishlistSerializer,
    WishlistSummarySerializer,
    WishlistToggleResultSerializer,
    WishlistWriteSerializer,
)
from common.identity import resolve_customer
from common.views import BaseModelViewSet


# ---------------------------------------------------------------------------
# Customer-facing endpoints
# ---------------------------------------------------------------------------
class MyWishlistView(APIView):
    """The caller's default wishlist.

    Round 27: this endpoint belongs to an account, so it says so. Without the
    permission class an expired token fell through to the identity seam, which
    tried to resolve a customer from a token it could not verify and reported
    `not_found` (404) - indistinguishable, to the client, from "this route does
    not exist". Declaring the requirement turns that into a clean 401, which the
    storefront already knows how to renew.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: WishlistSerializer}, tags=["Wishlist"])
    def get(self, request):
        customer = resolve_customer(request)
        wishlist = services.get_or_create_default_wishlist(customer)
        return Response(WishlistSerializer(wishlist, context={"request": request}).data)


class WishlistToggleView(APIView):
    """Add/remove a product from the default wishlist in one call."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ToggleWishlistItemSerializer,
        responses={200: WishlistToggleResultSerializer},
        tags=["Wishlist"],
    )
    def post(self, request):
        customer = resolve_customer(request)
        serializer = ToggleWishlistItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_product_or_404(serializer.validated_data["product"])
        result = services.toggle_wishlist_item(customer, product)
        return Response(WishlistToggleResultSerializer(result).data)


# ---------------------------------------------------------------------------
# Full CRUD
# ---------------------------------------------------------------------------
class WishlistViewSet(BaseModelViewSet):
    """CRUD API for wishlists."""

    search_fields = ("name", "customer__full_name", "customer__mobile_number")
    ordering_fields = ("created_at", "name")
    ordering = ("-is_default", "name")
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        customer = self.request.query_params.get("customer")
        return selectors.list_wishlists(customer=customer)

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return WishlistWriteSerializer
        return WishlistSerializer

    def get_object(self):
        wishlist = services.get_wishlist_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, wishlist)
        return wishlist

    def create(self, request, *args, **kwargs):
        customer = resolve_customer(request)
        serializer = WishlistWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wishlist = services.create_wishlist(customer, **serializer.validated_data)
        return Response(
            WishlistSerializer(wishlist, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        wishlist = self.get_object()
        serializer = WishlistWriteSerializer(
            wishlist, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        updated = services.update_wishlist(wishlist, **serializer.validated_data)
        return Response(WishlistSerializer(updated, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_wishlist(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=AddWishlistItemSerializer,
        responses={201: WishlistItemSerializer},
        description="Add a product to this wishlist.",
    )
    @action(detail=True, methods=["post"], url_path="items")
    def add_item(self, request, pk=None):
        wishlist = self.get_object()
        serializer = AddWishlistItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_product_or_404(serializer.validated_data["product"])
        item = services.add_to_wishlist(
            wishlist.customer,
            product,
            wishlist=wishlist,
            notes=serializer.validated_data.get("notes", ""),
        )
        return Response(
            WishlistItemSerializer(item, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(responses={200: WishlistSummarySerializer})
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        customer = resolve_customer(request, required=False)
        return Response(
            WishlistSummarySerializer(selectors.wishlist_summary(customer)).data
        )


class WishlistItemViewSet(BaseModelViewSet):
    """CRUD API for individual wishlist entries."""

    search_fields = ("product__name",)
    ordering_fields = ("created_at",)
    ordering = ("-created_at",)
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        queryset = selectors.wishlist_item_queryset()
        wishlist_id = self.request.query_params.get("wishlist")
        if wishlist_id:
            queryset = queryset.filter(wishlist_id=wishlist_id)
        customer = self.request.query_params.get("customer")
        if customer:
            queryset = queryset.filter(wishlist__customer_id=customer)
        return queryset

    def get_serializer_class(self):
        return WishlistItemSerializer

    def get_object(self):
        item = services.get_wishlist_item_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, item)
        return item

    def create(self, request, *args, **kwargs):
        customer = resolve_customer(request)
        serializer = AddWishlistItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_product_or_404(serializer.validated_data["product"])
        wishlist = None
        if serializer.validated_data.get("wishlist"):
            wishlist = services.get_wishlist_or_404(serializer.validated_data["wishlist"])
        item = services.add_to_wishlist(
            customer, product, wishlist=wishlist,
            notes=serializer.validated_data.get("notes", ""),
        )
        return Response(
            WishlistItemSerializer(item, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        services.remove_wishlist_item(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=MoveToCartSerializer,
        responses={201: dict},
        description="Move this wishlist entry into the cart.",
    )
    @action(detail=True, methods=["post"], url_path="move-to-cart")
    def move_to_cart(self, request, pk=None):
        item = self.get_object()
        serializer = MoveToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart_item = services.move_to_cart(
            item, quantity=serializer.validated_data["quantity"]
        )
        return Response(
            {"message": "Moved to cart.", "cart_item_id": cart_item.id},
            status=status.HTTP_201_CREATED,
        )
