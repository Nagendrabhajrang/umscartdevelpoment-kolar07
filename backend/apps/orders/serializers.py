"""Serializers for orders."""


from rest_framework import serializers

from apps.orders.models import (
    CancellationReason,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentMethod,
)


class OrderItemSerializer(serializers.ModelSerializer):
    product_image_url = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "id", "uid", "product", "product_name", "product_sku", "unit_label",
            "quantity", "unit_mrp", "unit_price", "line_total", "line_savings",
            "tax_percent", "product_image_url",
        )
        read_only_fields = fields

    def get_product_image_url(self, obj) -> str | None:
        if obj.product_image:
            request = self.context.get("request")
            try:
                url = obj.product_image.url
            except ValueError:
                return None
            return url  # relative: /media is proxied by the frontend
        if obj.product and obj.product.image:
            request = self.context.get("request")
            try:
                url = obj.product.image.url
            except ValueError:
                return None
            return url  # relative: /media is proxied by the frontend
        return None


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    to_status_display = serializers.CharField(source="get_to_status_display", read_only=True)
    from_status_display = serializers.CharField(
        source="get_from_status_display", read_only=True
    )

    class Meta:
        model = OrderStatusHistory
        fields = (
            "id", "from_status", "from_status_display", "to_status",
            "to_status_display", "note", "changed_by", "created_at",
        )
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_mobile = serializers.CharField(source="customer.mobile_number", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    item_count = serializers.IntegerField(read_only=True)
    # The list needs these three to decide whether "Mark delivered" is legal:
    # without them every row looked unpaid and the actions never matched state.
    next_statuses = serializers.ListField(child=serializers.CharField(), read_only=True)
    is_paid = serializers.BooleanField(read_only=True)
    payment_id = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id", "uid", "order_number", "customer", "customer_name", "customer_mobile",
            "status", "status_display", "payment_method", "payment_method_display",
            "payment_status", "grand_total", "currency", "item_count",
            "total_quantity", "delivery_city", "next_statuses", "is_paid", "payment_id",
            "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_payment_id(self, obj):
        first = obj.payments.all().order_by("id").first()
        return first.id if first else None


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_mobile = serializers.CharField(source="customer.mobile_number", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    full_delivery_address = serializers.CharField(read_only=True)
    total_savings = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    next_statuses = serializers.ListField(child=serializers.CharField(), read_only=True)
    can_be_cancelled = serializers.BooleanField(read_only=True)
    is_paid = serializers.BooleanField(read_only=True)
    # The payment record backing this order - lets the admin jump from the
    # order straight to its cash row.
    payment_id = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id", "uid", "order_number", "customer", "customer_name",
            "customer_mobile", "address", "status", "status_display",
            "payment_method", "payment_method_display", "payment_status",
            "payment_status_display", "subtotal", "mrp_total", "product_savings",
            "discount_amount", "coupon_code", "promotion_name", "delivery_charge",
            "packaging_charge", "tax_amount", "grand_total", "total_savings",
            "currency", "item_count", "total_quantity", "items", "status_history",
            "delivery_recipient_name", "delivery_recipient_mobile",
            "delivery_address_line1", "delivery_address_line2", "delivery_landmark",
            "delivery_city", "delivery_state", "delivery_pincode", "delivery_country",
            "delivery_label", "delivery_instructions", "full_delivery_address",
            "customer_notes", "internal_notes", "delivery_eta_minutes",
            "confirmed_at", "delivered_at", "cancelled_at", "cancellation_reason",
            "cancellation_note", "next_statuses", "can_be_cancelled", "is_paid",
            "payment_id", "created_at", "updated_at",
        )
        read_only_fields = fields


    def get_payment_id(self, obj):
        payment = getattr(obj, "_payment_row", None)
        if payment is None:
            first = obj.payments.all().order_by("id").first()
            return first.id if first else None
        return payment.id if payment else None


class CheckoutSerializer(serializers.Serializer):
    """Payload for POST /orders/checkout/."""

    address = serializers.IntegerField(min_value=1)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    customer_notes = serializers.CharField(
        required=False, allow_blank=True, max_length=1000, default=""
    )
    coupon_code = serializers.CharField(
        required=False, allow_blank=True, max_length=40, allow_null=True
    )


class GuestCheckoutSerializer(serializers.Serializer):
    """Payload for the signed-out checkout (round 25).

    The storefront no longer has a login, so the order carries everything it
    needs: who is receiving it, where, and one contact number that becomes the
    customer record for future lookups.
    """

    recipient_name = serializers.CharField(max_length=150)
    mobile_number = serializers.CharField(max_length=20)
    line1 = serializers.CharField(max_length=255, help_text="House / flat / building")
    line2 = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )
    landmark = serializers.CharField(
        required=False, allow_blank=True, max_length=150, default=""
    )
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    pincode = serializers.CharField(max_length=10)
    delivery_instructions = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    customer_notes = serializers.CharField(
        required=False, allow_blank=True, max_length=1000, default=""
    )

    def validate_mobile_number(self, value):
        from common.validators import canonical_mobile, is_indian_mobile

        if not is_indian_mobile(value or ""):
            raise serializers.ValidationError("Enter a valid 10-digit mobile number.")
        return canonical_mobile(value)

    def validate_pincode(self, value):
        from common.validators import validate_pincode

        validate_pincode(value)
        return value


class CheckoutPreviewSerializer(serializers.Serializer):
    address = serializers.IntegerField(min_value=1, required=False)
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices, required=False, default=PaymentMethod.COD
    )


class OrderCreateSerializer(serializers.ModelSerializer):
    """Direct order creation (admin / POS use)."""

    items = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=True
    )

    class Meta:
        model = Order
        fields = (
            "customer", "address", "payment_method", "customer_notes",
            "internal_notes", "items",
        )

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        for index, entry in enumerate(value):
            product_id = entry.get("product")
            quantity = entry.get("quantity", 1)
            if not product_id:
                raise serializers.ValidationError(
                    f"Item {index + 1}: 'product' is required."
                )
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    f"Item {index + 1}: 'quantity' must be an integer."
                )
            if quantity < 1:
                raise serializers.ValidationError(
                    f"Item {index + 1}: 'quantity' must be at least 1."
                )
        return value


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    changed_by = serializers.CharField(
        required=False, allow_blank=True, max_length=150, default="admin"
    )


class OrderCancelSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(
        choices=CancellationReason.choices, default=CancellationReason.CUSTOMER_REQUEST
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    changed_by = serializers.CharField(
        required=False, allow_blank=True, max_length=150, default="customer"
    )


class OrderNotesSerializer(serializers.Serializer):
    internal_notes = serializers.CharField(allow_blank=True, max_length=2000)


class OrderStatsSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    cancelled_orders = serializers.IntegerField()
    delivered_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    cod_orders = serializers.IntegerField()
    upi_orders = serializers.IntegerField()
    average_order_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    fulfilment_rate = serializers.FloatField()


class ReorderResultSerializer(serializers.Serializer):
    added = serializers.ListField(child=serializers.DictField())
    skipped = serializers.ListField(child=serializers.DictField())
