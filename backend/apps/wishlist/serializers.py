"""Serializers for the wishlist app."""

from rest_framework import serializers

from apps.wishlist.models import Wishlist, WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    selling_price = serializers.DecimalField(
        source="product.selling_price", max_digits=12, decimal_places=2, read_only=True
    )
    mrp = serializers.DecimalField(
        source="product.mrp", max_digits=12, decimal_places=2, read_only=True
    )
    image_url = serializers.SerializerMethodField()
    available_quantity = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    is_purchasable = serializers.BooleanField(source="product.is_purchasable", read_only=True)

    class Meta:
        model = WishlistItem
        fields = (
            "id", "uid", "wishlist", "product", "product_name", "product_slug",
            "product_sku", "selling_price", "mrp", "image_url",
            "available_quantity", "in_stock", "is_purchasable", "notes",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "uid", "created_at", "updated_at")

    def get_image_url(self, obj) -> str | None:
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
        return stock.quantity_available if stock else 0

    def get_in_stock(self, obj) -> bool:
        return self.get_available_quantity(obj) > 0


class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)

    class Meta:
        model = Wishlist
        fields = (
            "id", "uid", "customer", "customer_name", "name", "is_default",
            "is_public", "items", "item_count", "created_at", "updated_at",
        )
        read_only_fields = ("id", "uid", "created_at", "updated_at")


class WishlistWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wishlist
        fields = ("name", "is_public")

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Wishlist name cannot be empty.")
        return value


class AddWishlistItemSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    wishlist = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class ToggleWishlistItemSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)


class WishlistToggleResultSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    is_wishlisted = serializers.BooleanField()
    message = serializers.CharField()


class MoveToCartSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1)


class WishlistSummarySerializer(serializers.Serializer):
    total_wishlists = serializers.IntegerField()
    total_items = serializers.IntegerField()
