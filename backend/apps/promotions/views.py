"""Promotion API views.

SECURITY NOTE: authentication is not implemented in this phase. These
endpoints are unrestricted and must NOT be exposed publicly until the
authentication layer ships.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.promotions import selectors, services
from apps.promotions.filters import CouponRedemptionFilter, PromotionFilter
from apps.promotions.serializers import (
    CouponApplySerializer,
    CouponRedemptionSerializer,
    CouponValidationResultSerializer,
    PromotionSerializer,
    PromotionSummarySerializer,
    PromotionToggleSerializer,
    PromotionWriteSerializer,
)
from common.exceptions import BusinessRuleError
from common.identity import resolve_customer
from common.views import BaseModelViewSet, BaseReadOnlyViewSet


class PromotionViewSet(BaseModelViewSet):
    """CRUD API for offers and coupon codes."""

    filterset_class = PromotionFilter
    search_fields = ("name", "code", "description")
    ordering_fields = ("created_at", "priority", "start_date", "end_date", "used_count")
    ordering = ("-priority", "display_order")
    # Numeric id, public UUID, or human coupon code (e.g. "SAVE10").
    lookup_value_regex = r"[A-Za-z0-9_-]{1,64}"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_promotions(
            {
                "is_active": _to_bool(params.get("is_active")),
                "kind": params.get("kind"),
                "code": params.get("code"),
                "currently_valid": _to_bool(params.get("currently_valid")),
                "search": params.get("search"),
            }
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return PromotionWriteSerializer
        return PromotionSerializer

    def get_object(self):
        promotion = services.get_promotion_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, promotion)
        return promotion

    def create(self, request, *args, **kwargs):
        serializer = PromotionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        promotion = services.create_promotion(**dict(serializer.validated_data))
        return Response(
            PromotionSerializer(promotion, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        promotion = self.get_object()
        serializer = PromotionWriteSerializer(
            promotion, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        updated = services.update_promotion(promotion, **dict(serializer.validated_data))
        return Response(PromotionSerializer(updated, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_promotion(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=PromotionToggleSerializer, responses={200: PromotionSerializer}
    )
    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        promotion = self.get_object()
        serializer = PromotionToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.toggle_promotion(
            promotion, serializer.validated_data["is_active"]
        )
        return Response(PromotionSerializer(updated).data)

    @extend_schema(
        responses={200: PromotionSerializer(many=True)},
        description="Offers visible on the storefront right now.",
    )
    @action(detail=False, methods=["get"], url_path="active-offers")
    def active_offers(self, request):
        return Response(
            PromotionSerializer(
                selectors.list_visible_offers(), many=True, context={"request": request}
            ).data
        )

    @extend_schema(responses={200: PromotionSummarySerializer})
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        return Response(PromotionSummarySerializer(selectors.promotion_summary()).data)


class CouponViewSet(BaseReadOnlyViewSet):
    """Customer-facing coupon validation endpoint."""

    def get_queryset(self):
        return selectors.list_promotions({"kind": "coupon"})

    def get_serializer_class(self):
        return PromotionSerializer

    @extend_schema(
        request=CouponApplySerializer,
        responses={200: CouponValidationResultSerializer},
        description=(
            "Evaluate a coupon code against the caller's cart without "
            "redeeming it. Returns the discount that would apply."
        ),
    )
    @action(detail=False, methods=["post"], url_path="validate")
    def validate_coupon(self, request):
        from apps.cart import selectors as cart_selectors

        serializer = CouponApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = resolve_customer(request, required=False)
        if customer is None:
            raise BusinessRuleError(
                message="A customer context is required to validate a coupon.",
                code="customer_context_required",
            )

        cart = cart_selectors.get_active_cart(customer)
        if cart is None or not cart.items.exists():
            raise BusinessRuleError(
                message="Your cart is empty.", code="empty_cart"
            )

        items = list(cart.items.select_related("product", "product__category"))
        result = services.evaluate_coupon(
            serializer.validated_data["code"], customer, items, cart.subtotal
        )
        payload = result.as_dict()
        payload["is_valid"] = result.applied
        return Response(payload)

    @extend_schema(
        responses={200: PromotionSerializer(many=True)},
        description="All currently valid coupon codes.",
    )
    @action(detail=False, methods=["get"], url_path="available")
    def available(self, request):
        promotions = selectors.list_visible_offers().filter(code__isnull=False)
        return Response(
            PromotionSerializer(promotions, many=True, context={"request": request}).data
        )


class CouponRedemptionViewSet(BaseReadOnlyViewSet):
    """Read-only audit trail of coupon redemptions."""

    filterset_class = CouponRedemptionFilter
    ordering_fields = ("redeemed_at", "discount_amount")
    ordering = ("-redeemed_at",)
    # Numeric id, public UUID, or human coupon code (e.g. "SAVE10").
    lookup_value_regex = r"[A-Za-z0-9_-]{1,64}"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_redemptions(
            {
                "promotion": params.get("promotion"),
                "customer": params.get("customer"),
                "order": params.get("order"),
            }
        )

    def get_serializer_class(self):
        return CouponRedemptionSerializer


def _to_bool(value):
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
