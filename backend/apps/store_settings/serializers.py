"""Serializers for store settings."""

from decimal import Decimal

from rest_framework import serializers

from apps.store_settings.models import DeliverySlab, StoreHoliday, StoreSettings


class StoreSettingsSerializer(serializers.ModelSerializer):
    upi_qr_image_url = serializers.SerializerMethodField()

    class Meta:
        model = StoreSettings
        fields = "__all__"
        read_only_fields = ("id", "uid", "created_at", "updated_at")

    def get_upi_qr_image_url(self, obj) -> str | None:
        if not obj.upi_qr_image:
            return None
        request = self.context.get("request")
        try:
            url = obj.upi_qr_image.url
        except ValueError:
            return None
        return url  # relative: /media is proxied by the frontend

    def validate(self, attrs):
        minimum = attrs.get(
            "minimum_order_value", getattr(self.instance, "minimum_order_value", Decimal("0"))
        )
        free_threshold = attrs.get(
            "free_delivery_threshold",
            getattr(self.instance, "free_delivery_threshold", Decimal("0")),
        )
        if free_threshold and minimum and free_threshold < minimum:
            raise serializers.ValidationError(
                {
                    "free_delivery_threshold": (
                        "The free delivery threshold cannot be lower than the "
                        "minimum order value."
                    )
                }
            )
        if not attrs.get("cod_enabled", getattr(self.instance, "cod_enabled", True)) and not attrs.get(
            "upi_enabled", getattr(self.instance, "upi_enabled", True)
        ):
            raise serializers.ValidationError(
                "At least one payment method (COD or UPI) must remain enabled."
            )
        return attrs


class StoreSettingsUpdateSerializer(serializers.ModelSerializer):
    """Partial update of the singleton settings.

    Cross-field invariants are validated here (rather than only in the model)
    so the API answers with the offending field and a 400 instead of leaking a
    Django ValidationError.
    """

    class Meta:
        model = StoreSettings
        fields = (
            "store_name", "tagline", "contact_phone", "contact_email", "address",
            "currency_code", "currency_symbol", "delivery_charge",
            "free_delivery_threshold", "minimum_order_value",
            "max_delivery_distance_km", "delivery_eta_minutes",
            "default_tax_percent", "packaging_charge", "apply_tax_on_delivery",
            "cod_enabled", "upi_enabled", "max_items_per_order", "order_prefix",
            "auto_cancel_unpaid_minutes", "upi_id", "upi_payee_name",
            "upi_qr_image", "cod_instructions", "is_store_open",
            "maintenance_message",
        )

    def _current(self, attrs, field_name):
        if field_name in attrs:
            return attrs[field_name]
        return getattr(self.instance, field_name, None)

    def validate(self, attrs):
        minimum = self._current(attrs, "minimum_order_value")
        free_threshold = self._current(attrs, "free_delivery_threshold")
        if (
            free_threshold is not None
            and minimum is not None
            and Decimal(str(free_threshold)) > 0
            and Decimal(str(free_threshold)) < Decimal(str(minimum))
        ):
            raise serializers.ValidationError(
                {
                    "free_delivery_threshold": (
                        "The free delivery threshold cannot be lower than the "
                        "minimum order value."
                    )
                }
            )

        if not self._current(attrs, "cod_enabled") and not self._current(
            attrs, "upi_enabled"
        ):
            raise serializers.ValidationError(
                {
                    "detail": (
                        "At least one payment method (COD or UPI) must remain "
                        "enabled."
                    )
                }
            )

        slab_min = self._current(attrs, "delivery_charge")
        if slab_min is not None and Decimal(str(slab_min)) < 0:
            raise serializers.ValidationError(
                {"delivery_charge": "Delivery charge cannot be negative."}
            )
        return attrs


class DeliverySlabSerializer(serializers.ModelSerializer):
    is_free = serializers.BooleanField(read_only=True)

    class Meta:
        model = DeliverySlab
        fields = (
            "id", "uid", "name", "min_order_value", "max_order_value",
            "delivery_charge", "is_free", "is_active", "display_order",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "uid", "created_at", "updated_at")

    def validate(self, attrs):
        minimum = attrs.get(
            "min_order_value", getattr(self.instance, "min_order_value", Decimal("0"))
        )
        maximum = attrs.get(
            "max_order_value", getattr(self.instance, "max_order_value", None)
        )
        if maximum is not None and maximum <= minimum:
            raise serializers.ValidationError(
                {"max_order_value": "The upper bound must be greater than the lower bound."}
            )
        return attrs


class StoreHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreHoliday
        fields = ("id", "uid", "date", "reason", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "uid", "created_at", "updated_at")

    def validate_date(self, value):
        queryset = StoreHoliday.objects.filter(date=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A holiday already exists for this date.")
        return value


class DeliveryChargeQuoteSerializer(serializers.Serializer):
    """Payload for the delivery-charge quote endpoint."""

    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))


class DeliveryChargeQuoteResultSerializer(serializers.Serializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    delivery_charge = serializers.DecimalField(max_digits=12, decimal_places=2)
    is_free_delivery = serializers.BooleanField()
    free_delivery_threshold = serializers.DecimalField(max_digits=12, decimal_places=2)
    applied_slab = serializers.CharField(allow_null=True)
    amount_to_free_delivery = serializers.DecimalField(max_digits=12, decimal_places=2)
    eta_minutes = serializers.IntegerField()
    minimum_order_value = serializers.DecimalField(max_digits=12, decimal_places=2)
