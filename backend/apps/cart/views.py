"""Cart API views.

SECURITY NOTE: authentication is not implemented in this phase. These
endpoints are unrestricted and must NOT be exposed publicly until the
authentication layer ships. Customer context comes from the
``X-Customer-Id`` header / ``customer`` query parameter.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart import selectors, services
from apps.cart.filters import CartFilter
from apps.cart.serializers import (
    AddToCartSerializer,
    CartItemSerializer,
    CartSerializer,
    CartSummaryCountersSerializer,
    CartSummarySerializer,
    CouponCodeSerializer,
    UpdateCartItemSerializer,
)
from apps.catalog.services import get_product_or_404
from common.exceptions import BusinessRuleError
from common.identity import resolve_customer
from common.views import BaseReadOnlyViewSet

GUEST_KEY_HEADER = "X-Guest-Cart"


def _guest_key(request) -> str:
    """The browser's anonymous basket key, if it sent one."""
    raw = request.META.get("HTTP_X_GUEST_CART", "")
    if not raw:
        raw = request.query_params.get("guest_cart", "")
    if not raw:
        data = getattr(request, "data", None)
        if isinstance(data, dict):
            raw = data.get("guest_cart") or data.get("guest_key") or ""
    return services.normalise_guest_key(raw)


def _owner(request):
    """Return ``("customer", obj)`` or ``("guest", key)``.

    Round 23: the storefront lets a shopper build a cart before signing in, so a
    cart request no longer implies an account. A signed-in customer always wins;
    otherwise the browser's guest key names the basket.
    """
    customer = resolve_customer(request, required=False)
    if customer is not None:
        return "customer", customer
    key = _guest_key(request)
    if key:
        return "guest", key
    raise BusinessRuleError(
        message=(
            "We could not tell whose cart this is. Refresh the page and try again."
        ),
        code="customer_context_required",
    )


def _cart_for(request, create: bool = True):
    """Return the cart this request operates on (customer or guest)."""
    kind, owner = _owner(request)
    if kind == "customer":
        # Round 32: fold in a guest basket left by this browser *now*, on a
        # request that arrives with a working session. See
        # apps.authentication.services.auth_service.customer_verify_otp for why
        # this is not done inside the login call.
        services.adopt_guest_cart(_guest_key(request), owner)
        return services.get_or_create_active_cart(owner) if create else services.get_or_create_active_cart(owner), kind, owner
    cart = services.get_guest_cart(owner, create=create)
    if cart is None:
        raise BusinessRuleError(
            message="This cart is empty.", code="cart_not_found", status_code=404
        )
    return cart, kind, owner


def _assert_cart_access(request, cart):
    """A cart is reachable only by its owner. Prevents cross-basket access."""
    kind, owner = _owner(request)
    if kind == "customer":
        if cart.customer_id != owner.id:
            raise BusinessRuleError(
                message="This cart belongs to another customer.",
                code="cart_forbidden",
                status_code=403,
            )
    else:
        if cart.customer_id is not None or cart.guest_key != owner:
            raise BusinessRuleError(
                message="This cart belongs to another customer.",
                code="cart_forbidden",
                status_code=403,
            )
    return cart


# ---------------------------------------------------------------------------
# Customer-facing "my cart" endpoints
# ---------------------------------------------------------------------------
class MyCartView(APIView):
    """The caller's single active cart."""

    @extend_schema(
        responses={200: CartSerializer},
        tags=["Cart"],
        description="Return the caller's active cart, creating it if necessary.",
    )
    def get(self, request):
        cart, _, _ = _cart_for(request)
        return Response(CartSerializer(cart, context={"request": request}).data)

    @extend_schema(
        request=None, responses={204: None}, tags=["Cart"],
        description="Remove every item and any applied coupon from the cart.",
    )
    def delete(self, request):
        cart, _, _ = _cart_for(request)
        services.clear_cart(cart)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemCollectionView(APIView):
    """Add items to the active cart."""

    @extend_schema(
        request=AddToCartSerializer,
        responses={201: CartSerializer},
        tags=["Cart"],
        description="Add a product to the cart. Quantities merge for repeat products.",
    )
    def post(self, request):
        cart, kind, owner = _cart_for(request)
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = get_product_or_404(serializer.validated_data["product"])
        if kind == "customer":
            item = services.add_to_cart(
                owner,
                product,
                quantity=serializer.validated_data["quantity"],
                notes=serializer.validated_data.get("notes", ""),
            )
        else:
            # A guest basket has no Customer row; the line is added to the cart
            # directly so validation, stock checks and price snapshots are the
            # same code path a signed-in shopper uses.
            item = services.add_item_to_cart(
                cart,
                product,
                quantity=serializer.validated_data["quantity"],
                notes=serializer.validated_data.get("notes", ""),
            )
        cart.refresh_from_db()
        return Response(
            {
                "item": CartItemSerializer(item, context={"request": request}).data,
                "cart": CartSerializer(cart, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CartItemDetailView(APIView):
    """Update or remove a single cart line."""

    def _get_item(self, request, item_id):
        item = services.get_cart_item_or_404(item_id)
        _assert_cart_access(request, item.cart)
        return item

    @extend_schema(
        request=UpdateCartItemSerializer, responses={200: CartSerializer}, tags=["Cart"]
    )
    def patch(self, request, item_id):
        item = self._get_item(request, item_id)
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = item.cart
        services.update_cart_item(
            item,
            serializer.validated_data["quantity"],
            serializer.validated_data.get("notes"),
        )
        cart.refresh_from_db()
        return Response(CartSerializer(cart, context={"request": request}).data)

    @extend_schema(responses={204: None}, tags=["Cart"])
    def delete(self, request, item_id):
        item = self._get_item(request, item_id)
        cart = item.cart
        services.remove_cart_item(item)
        cart.refresh_from_db()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemIncrementView(APIView):
    """Convenience +/- endpoints for the mobile clients."""

    def _item(self, request, item_id):
        item = services.get_cart_item_or_404(item_id)
        _assert_cart_access(request, item.cart)
        return item

    @extend_schema(request=None, responses={200: CartSerializer}, tags=["Cart"])
    def post(self, request, item_id):
        item = self._item(request, item_id)
        cart = item.cart
        services.increment_cart_item(item, 1)
        cart.refresh_from_db()
        return Response(CartSerializer(cart, context={"request": request}).data)


class CartItemDecrementView(APIView):
    @extend_schema(request=None, responses={200: CartSerializer}, tags=["Cart"])
    def post(self, request, item_id):
        item = services.get_cart_item_or_404(item_id)
        _assert_cart_access(request, item.cart)
        cart = item.cart
        if item.quantity <= 1:
            services.remove_cart_item(item)
        else:
            services.increment_cart_item(item, -1)
        cart.refresh_from_db()
        return Response(CartSerializer(cart, context={"request": request}).data)


class CartSummaryView(APIView):
    """Full price breakdown for the active cart."""

    @extend_schema(responses={200: CartSummarySerializer}, tags=["Cart"])
    def get(self, request):
        cart, _, _ = _cart_for(request)
        return Response(CartSummarySerializer(services.build_cart_summary(cart)).data)


class CartCouponView(APIView):
    """Apply or remove a coupon on the active cart."""

    @extend_schema(request=CouponCodeSerializer, responses={200: CartSummarySerializer}, tags=["Cart"])
    def post(self, request):
        cart, _, _ = _cart_for(request)
        serializer = CouponCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.apply_coupon(cart, serializer.validated_data["code"])
        cart.refresh_from_db()
        return Response(CartSummarySerializer(services.build_cart_summary(cart)).data)

    @extend_schema(responses={200: CartSummarySerializer}, tags=["Cart"])
    def delete(self, request):
        cart, _, _ = _cart_for(request)
        services.remove_coupon(cart)
        cart.refresh_from_db()
        return Response(CartSummarySerializer(services.build_cart_summary(cart)).data)


class CartMergeView(APIView):
    """Merge another cart (e.g. a guest cart) into the active cart."""

    @extend_schema(
        request=None,
        parameters=[OpenApiParameter("source_cart", int, required=True)],
        responses={200: CartSerializer},
        tags=["Cart"],
    )
    def post(self, request):
        """Fold the browser's guest basket into the signed-in account's cart.

        This is what runs right after a successful login. It is idempotent: the
        guest basket is marked ``merged`` in the same transaction, so a retry or
        a second tab cannot add the items twice.
        """
        customer = resolve_customer(request)
        guest_key = _guest_key(request)
        if not guest_key:
            cart = services.get_or_create_active_cart(customer)
            return Response(CartSerializer(cart, context={"request": request}).data)

        cart, moved = services.merge_guest_cart_into(guest_key, customer)
        data = CartSerializer(cart, context={"request": request}).data
        data["merged_line_count"] = moved
        return Response(data)


# ---------------------------------------------------------------------------
# Admin/back-office carts
# ---------------------------------------------------------------------------
class CartViewSet(BaseReadOnlyViewSet):
    """Administrative read access to carts (all customers)."""

    filterset_class = CartFilter
    search_fields = ("customer__full_name", "customer__mobile_number", "coupon_code")
    ordering_fields = ("created_at", "last_activity_at")
    ordering = ("-last_activity_at",)
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_carts(
            {
                "status": params.get("status"),
                "customer": params.get("customer"),
                "search": params.get("search"),
            }
        )

    def get_serializer_class(self):
        return CartSerializer

    def get_object(self):
        cart = services.get_cart_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, cart)
        return cart

    @extend_schema(responses={200: CartSummarySerializer})
    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
        cart = self.get_object()
        return Response(CartSummarySerializer(services.build_cart_summary(cart)).data)

    @extend_schema(
        request=None, responses={200: CartSerializer},
        description="Refresh all line prices to the current product prices.",
    )
    @action(detail=True, methods=["post"], url_path="refresh-prices")
    def refresh_prices(self, request, pk=None):
        cart = services.refresh_cart_prices(self.get_object())
        cart.refresh_from_db()
        return Response(CartSerializer(cart, context={"request": request}).data)

    @extend_schema(
        request=None, responses={200: CartSerializer},
        description="Mark an inactive cart as abandoned.",
    )
    @action(detail=True, methods=["post"], url_path="abandon")
    def abandon(self, request, pk=None):
        cart = services.abandon_cart(self.get_object())
        return Response(CartSerializer(cart, context={"request": request}).data)

    @extend_schema(responses={200: CartSummaryCountersSerializer})
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        return Response(CartSummaryCountersSerializer(selectors.cart_summary()).data)
