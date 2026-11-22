"""Serializers for inventory."""

from rest_framework import serializers

from apps.inventory.models import InventoryLog, Stock, StockMovementType


class StockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    quantity_available = serializers.IntegerField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Stock
        fields = (
            "id", "uid", "product", "product_name", "product_sku", "quantity",
            "reserved_quantity", "quantity_available", "low_stock_threshold",
            "track_inventory", "is_low_stock", "is_out_of_stock",
            "created_at", "updated_at",
        )
        read_only_fields = (
            # Stock levels are only ever changed through the add / remove /
            # adjust service functions, which also write a movement record.
            "id", "uid", "quantity_available", "reserved_quantity",
            "created_at", "updated_at",
        )


class StockUpdateSerializer(serializers.Serializer):
    """Payload for the absolute stock adjustment endpoint."""

    quantity = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    performed_by = serializers.CharField(required=False, allow_blank=True, default="")


class StockAdjustSerializer(serializers.Serializer):
    """Payload for relative stock changes (+/-)."""

    quantity = serializers.IntegerField(min_value=1)
    movement_type = serializers.ChoiceField(
        choices=StockMovementType.choices,
        default=StockMovementType.ADJUSTMENT,
        required=False,
    )
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    performed_by = serializers.CharField(required=False, allow_blank=True, default="")


class StockThresholdSerializer(serializers.Serializer):
    low_stock_threshold = serializers.IntegerField(min_value=0)


class TrackInventorySerializer(serializers.Serializer):
    track_inventory = serializers.BooleanField()


class InventoryLogSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    movement_type_display = serializers.CharField(
        source="get_movement_type_display", read_only=True
    )

    class Meta:
        model = InventoryLog
        fields = (
            "id", "uid", "stock", "product", "product_name", "product_sku",
            "movement_type", "movement_type_display", "quantity_change",
            "quantity_before", "quantity_after", "reference", "reason",
            "performed_by", "created_at",
        )
        read_only_fields = fields


class StockCheckSerializer(serializers.Serializer):
    product = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class StockCheckResultSerializer(serializers.Serializer):
    product = serializers.IntegerField()
    requested = serializers.IntegerField()
    available = serializers.IntegerField()
    is_available = serializers.BooleanField()
    track_inventory = serializers.BooleanField()


class InventorySummarySerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    total_units = serializers.IntegerField()
    out_of_stock = serializers.IntegerField()
    low_stock = serializers.IntegerField()


class StockDiscrepancySerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    recorded_quantity = serializers.IntegerField()
    movement_total = serializers.IntegerField()
    difference = serializers.IntegerField()
