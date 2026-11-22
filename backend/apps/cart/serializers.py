"""Serializers for the cart app."""


from rest_framework import serializers

from apps.cart.models import Cart, CartItem, CartStatus


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_image = serializers.SerializerMethodField()
    unit_label = serializers.CharField(source="product.unit_label", read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    line_mrp_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    line_savings = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    available_quantity = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    price_changed = serializers.BooleanField(read_only=True)
    current_price = serializers.DecimalField(
        source="product.selling_price", max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = CartItem
        fields = (
            "id", "uid", "cart", "product", "product_name", "product_slug",
            "product_sku", "product_image", "unit_label", "quantity", "unit_price",
            "unit_mrp", "current_price", "line_total", "line_mrp_total",
            "line_savings", "available_quantity", "is_available", "price_changed",
            "product_name_snapshot", "notes", "added_at", "updated_at",
        )
        read_only_fields = (
            "id", "uid", "unit_price", "unit_mrp", "added_at", "updated_at",
        )

    def get_product_image(self, obj) -> str | None:
        if not obj.product.image:
            return None
        request = self.context.get("request")
        try:
            url = obj.product.image.url
        except ValueError:
            return None
        return url  # relative: /media is proxied by the frontend

    def get_available_quantity(self, obj) -> int:
        stock = getattr(obj.product, "stock", None)
        if stock is None:
            return 0
        return stock.quantity_available

    def get_is_available(self, obj) -> bool:
        stock = getattr(obj.product, "stock", None)
        if stock is None:
            return False
        if not stock.track_inventory:
            return True
        return stock.quantity_available >= obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_mobile = serializers.CharField(source="customer.mobile_number", read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    mrp_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    savings = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = (
            "id", "uid", "customer", "customer_name", "customer_mobile", "status",
            "coupon_code", "notes", "items", "item_count", "total_quantity",
            "subtotal", "mrp_total", "savings", "last_activity_at",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "uid", "created_at", "updated_at", "last_activity_at")


class AddToCartSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0, max_value=999)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)


class CartItemQuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class CouponCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=40)


class CartSummarySerializer(serializers.Serializer):
    """Response shape of GET /cart/summary/ and POST /orders/checkout/preview/."""

    cart_id = serializers.IntegerField()
    cart_uid = serializers.CharField()
    status = serializers.CharField()
    item_count = serializers.IntegerField()
    total_quantity = serializers.IntegerField()
    currency = serializers.CharField()
    currency_symbol = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    mrp_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    product_savings = serializers.DecimalField(max_digits=12, decimal_places=2)
    coupon_code = serializers.CharField(allow_null=True)
    applied_promotion = serializers.DictField(allow_null=True)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    discounted_subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    delivery_charge = serializers.DecimalField(max_digits=12, decimal_places=2)
    is_free_delivery = serializers.BooleanField()
    free_delivery_threshold = serializers.DecimalField(max_digits=12, decimal_places=2)
    amount_to_free_delivery = serializers.DecimalField(max_digits=12, decimal_places=2)
    packaging_charge = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax_percent = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    minimum_order_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    minimum_order_met = serializers.BooleanField()
    next_step = serializers.CharField()
    issues = serializers.ListField(child=serializers.DictField())
    store_open = serializers.BooleanField()


class CartSummaryCountersSerializer(serializers.Serializer):
    total_carts = serializers.IntegerField()
    active_carts = serializers.IntegerField()
    abandoned_carts = serializers.IntegerField()
    converted_carts = serializers.IntegerField()
    total_items = serializers.IntegerField()
    total_units = serializers.IntegerField()


class CartStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=CartStatus.choices)
