"""Inventory API views.

SECURITY NOTE: authentication is not implemented in this phase. These
endpoints (stock adjustments especially) are unrestricted and must NOT be
exposed publicly until the authentication layer ships.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.inventory import selectors, services
from apps.inventory.filters import InventoryLogFilter, StockFilter
from apps.inventory.models import StockMovementType
from apps.inventory.serializers import (
    InventoryLogSerializer,
    InventorySummarySerializer,
    StockAdjustSerializer,
    StockSerializer,
    StockThresholdSerializer,
    StockUpdateSerializer,
    TrackInventorySerializer,
)
from common.views import BaseModelViewSet, BaseReadOnlyViewSet


class StockViewSet(BaseModelViewSet):
    """Read stock levels and perform audited adjustments."""

    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_class = StockFilter
    search_fields = ("product__name", "product__sku", "product__brand")
    ordering_fields = ("quantity", "updated_at", "product__name")
    ordering = ("product__name",)
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_stock(
            {
                "search": params.get("search"),
                "category": params.get("category"),
                "low_stock": _to_bool(params.get("low_stock")),
                "out_of_stock": _to_bool(params.get("out_of_stock")),
            }
        )

    def get_serializer_class(self):
        return StockSerializer

    def get_object(self):
        stock = services.get_stock_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, stock)
        return stock

    def create(self, request, *args, **kwargs):
        return Response(
            {
                "error": {
                    "code": "method_not_allowed",
                    "message": "Stock rows are created automatically with their product.",
                    "status": 405,
                }
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @extend_schema(
        request=StockAdjustSerializer,
        responses={200: StockSerializer},
        description="Add stock (goods received, returns) with an audit-log entry.",
    )
    @action(detail=True, methods=["post"], url_path="add")
    def add(self, request, pk=None):
        stock = self.get_object()
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        updated = services.add_stock(
            stock.product,
            data["quantity"],
            movement_type=data.get("movement_type", StockMovementType.PURCHASE),
            reference=data.get("reference", ""),
            reason=data.get("reason", ""),
            performed_by=data.get("performed_by", ""),
        )
        return Response(StockSerializer(updated).data)

    @extend_schema(
        request=StockAdjustSerializer,
        responses={200: StockSerializer},
        description="Remove stock (damage, wastage) with an audit-log entry.",
    )
    @action(detail=True, methods=["post"], url_path="remove")
    def remove(self, request, pk=None):
        stock = self.get_object()
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        updated = services.remove_stock(
            stock.product,
            data["quantity"],
            movement_type=data.get("movement_type", StockMovementType.DAMAGE),
            reference=data.get("reference", ""),
            reason=data.get("reason", ""),
            performed_by=data.get("performed_by", ""),
        )
        return Response(StockSerializer(updated).data)

    @extend_schema(
        request=StockUpdateSerializer,
        responses={200: StockSerializer},
        description="Set the on-hand quantity to an absolute value (stock count).",
    )
    @action(detail=True, methods=["patch"], url_path="quantity")
    def set_quantity(self, request, pk=None):
        stock = self.get_object()
        serializer = StockUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.adjust_stock(
            stock.product,
            serializer.validated_data["quantity"],
            reason=serializer.validated_data.get("reason", ""),
            performed_by=serializer.validated_data.get("performed_by", ""),
        )
        return Response(StockSerializer(updated).data)

    @extend_schema(
        request=StockThresholdSerializer, responses={200: StockSerializer}
    )
    @action(detail=True, methods=["patch"], url_path="threshold")
    def set_threshold(self, request, pk=None):
        stock = self.get_object()
        serializer = StockThresholdSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.set_low_stock_threshold(
            stock.product, serializer.validated_data["low_stock_threshold"]
        )
        return Response(StockSerializer(updated).data)

    @extend_schema(request=TrackInventorySerializer, responses={200: StockSerializer})
    @action(detail=True, methods=["patch"], url_path="tracking")
    def set_tracking(self, request, pk=None):
        stock = self.get_object()
        serializer = TrackInventorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.toggle_tracking(
            stock, serializer.validated_data["track_inventory"]
        )
        return Response(StockSerializer(updated).data)

    @extend_schema(
        responses={200: InventoryLogSerializer(many=True)},
        description="Movement history for this stock row.",
    )
    @action(detail=True, methods=["get"], url_path="movements")
    def movements(self, request, pk=None):
        stock = self.get_object()
        logs = stock.movements.select_related("product").all()[:200]
        page = self.paginate_queryset(logs)
        if page is not None:
            return self.get_paginated_response(
                InventoryLogSerializer(page, many=True).data
            )
        return Response(InventoryLogSerializer(logs, many=True).data)

    @extend_schema(
        responses={200: InventorySummarySerializer},
        description="Aggregate inventory counters.",
    )
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        return Response(InventorySummarySerializer(selectors.inventory_summary()).data)

    @extend_schema(
        responses={200: StockSerializer(many=True)},
        description="Products at or below their low-stock threshold.",
    )
    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        queryset = selectors.low_stock_products()
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(StockSerializer(page, many=True).data)
        return Response(StockSerializer(queryset, many=True).data)


class InventoryLogViewSet(BaseReadOnlyViewSet):
    """Read-only audit trail of stock movements."""

    filterset_class = InventoryLogFilter
    search_fields = ("product__name", "reference", "reason")
    ordering_fields = ("created_at", "quantity_change")
    ordering = ("-created_at",)
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_movements(
            {
                "product": params.get("product"),
                "movement_type": params.get("movement_type"),
                "reference": params.get("reference"),
                "date_from": params.get("date_from"),
                "date_to": params.get("date_to"),
            }
        )

    def get_serializer_class(self):
        return InventoryLogSerializer


def _to_bool(value):
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
