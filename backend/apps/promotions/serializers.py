"""Serializers for promotions."""

from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product
from apps.promotions.models import AppliesTo, CouponRedemption, DiscountType, Promotion
from apps.promotions.validators import validate_coupon_code_format


class PromotionSerializer(serializers.ModelSerializer):
    discount_label = serializers.CharField(read_only=True)
    is_currently_valid = serializers.BooleanField(read_only=True)
    remaining_uses = serializers.IntegerField(read_only=True, allow_null=True)
    category_name = serializers.CharField(source="category.name", read_only=True, allow_null=True)

    class Meta:
        model = Promotion
        fields = (
            "id", "uid", "name", "code", "description", "discount_type",
            "discount_value", "max_discount_amount", "discount_label",
            "min_order_value", "min_item_quantity", "applies_to", "category",
            "category_name", "products", "start_date", "end_date",
            "usage_limit_total", "usage_limit_per_customer", "used_count",
            "remaining_uses", "first_order_only", "is_active", "is_visible",
            "is_currently_valid", "priority", "display_order",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "uid", "used_count", "created_at", "updated_at")


class PromotionWriteSerializer(serializers.ModelSerializer):
    products = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Product.objects.all(), required=False,
    )

    class Meta:
        model = Promotion
        fields = (
            "name", "code", "description", "discount_type", "discount_value",
            "max_discount_amount", "min_order_value", "min_item_quantity",
            "applies_to", "category", "products", "start_date", "end_date",
            "usage_limit_total", "usage_limit_per_customer", "first_order_only",
            "is_active", "is_visible", "priority", "display_order",
        )
        # Drop DRF's auto UniqueValidator so validate_code() can answer with a
        # 409 duplicate_coupon_code instead of a generic 400.
        extra_kwargs = {"code": {"validators": []}}

    def validate_code(self, value):
        if not value:
            return None
        value = value.strip().upper()
        if not validate_coupon_code_format(value):
            raise serializers.ValidationError(
                "Coupon codes must be 3-40 characters using letters, digits, '-' or '_'."
            )
        queryset = Promotion.objects.filter(code__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            from common.exceptions import ConflictError

            raise ConflictError(
                message="A promotion with this coupon code already exists.",
                code="duplicate_coupon_code",
                details={"code": value},
            )
        return value

    def validate_discount_value(self, value):
        if value is None:
            return value
        if value < 0:
            raise serializers.ValidationError("Discount value cannot be negative.")
        return value

    def validate(self, attrs):
        discount_type = attrs.get(
            "discount_type", getattr(self.instance, "discount_type", DiscountType.PERCENTAGE)
        )
        discount_value = attrs.get(
            "discount_value", getattr(self.instance, "discount_value", Decimal("0"))
        )
        applies_to = attrs.get("applies_to", getattr(self.instance, "applies_to", AppliesTo.ALL))
        category = attrs.get("category", getattr(self.instance, "category", None))

        if discount_type == DiscountType.PERCENTAGE and discount_value > 100:
            raise serializers.ValidationError(
                {"discount_value": "Percentage discount cannot exceed 100."}
            )
        if discount_type != DiscountType.FREE_DELIVERY and discount_value <= 0:
            raise serializers.ValidationError(
                {"discount_value": "A positive discount value is required for this discount type."}
            )
        if applies_to == AppliesTo.CATEGORY and category is None:
            raise serializers.ValidationError(
                {"category": "A category is required when applies_to is 'category'."}
            )
        if applies_to == AppliesTo.PRODUCTS and not attrs.get("products"):
            raise serializers.ValidationError(
                {"products": "At least one product is required when applies_to is 'products'."}
            )

        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be after the start date."}
            )

        max_discount = attrs.get(
            "max_discount_amount", getattr(self.instance, "max_discount_amount", None)
        )
        if discount_type == DiscountType.FIXED and max_discount is not None:
            if max_discount < discount_value:
                raise serializers.ValidationError(
                    {"max_discount_amount": "Cap cannot be lower than the flat discount."}
                )
        return attrs


class CouponApplySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=40)
    customer = serializers.IntegerField(required=False, allow_null=True)


class CouponRedemptionSerializer(serializers.ModelSerializer):
    promotion_name = serializers.CharField(source="promotion.name", read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True, allow_null=True)

    class Meta:
        model = CouponRedemption
        fields = (
            "id", "uid", "promotion", "promotion_name", "customer", "customer_name",
            "order", "order_number", "reference", "code_snapshot",
            "discount_amount", "redeemed_at", "created_at",
        )
        read_only_fields = fields


class CouponValidationResultSerializer(serializers.Serializer):
    promotion_id = serializers.IntegerField(allow_null=True)
    promotion_name = serializers.CharField(allow_null=True)
    code = serializers.CharField(allow_null=True)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    free_delivery = serializers.BooleanField()
    eligible_subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    message = serializers.CharField()
    is_valid = serializers.BooleanField()


class PromotionSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    coupons = serializers.IntegerField()
    expired = serializers.IntegerField()
    total_redemptions = serializers.IntegerField()


class PromotionToggleSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()
