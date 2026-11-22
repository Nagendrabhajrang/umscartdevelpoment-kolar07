"""Serializers for addresses."""

from rest_framework import serializers

from apps.addresses.models import Address, AddressLabel
from common.validators import normalise_mobile, validate_mobile_number, validate_pincode


class AddressSerializer(serializers.ModelSerializer):
    label_display = serializers.CharField(source="get_label_display", read_only=True)
    full_address = serializers.CharField(read_only=True)
    short_address = serializers.CharField(read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_mobile = serializers.CharField(source="customer.mobile_number", read_only=True)

    class Meta:
        model = Address
        fields = (
            "id", "uid", "customer", "customer_name", "customer_mobile", "label",
            "label_display", "recipient_name", "recipient_mobile", "line1", "line2",
            "landmark", "city", "state", "pincode", "country", "latitude",
            "longitude", "is_default", "delivery_instructions", "full_address",
            "short_address", "created_at", "updated_at",
        )
        read_only_fields = ("id", "uid", "created_at", "updated_at")


class AddressWriteSerializer(serializers.ModelSerializer):
    label = serializers.ChoiceField(choices=AddressLabel.choices, required=False)
    recipient_mobile = serializers.CharField(
        max_length=20, validators=[validate_mobile_number]
    )
    pincode = serializers.CharField(max_length=10, validators=[validate_pincode])

    class Meta:
        model = Address
        fields = (
            "id", "label", "recipient_name", "recipient_mobile", "line1", "line2",
            "landmark", "city", "state", "pincode", "country", "latitude",
            "longitude", "is_default", "delivery_instructions",
        )
        read_only_fields = ("id",)

    def validate_recipient_mobile(self, value):
        return normalise_mobile(value)

    def validate_line1(self, value):
        value = (value or "").strip()
        if len(value) < 3:
            raise serializers.ValidationError("Address line 1 must be at least 3 characters.")
        return value

    def validate_city(self, value):
        value = (value or "").strip()
        if len(value) < 2:
            raise serializers.ValidationError("Enter a valid city.")
        return value


class SetDefaultSerializer(serializers.Serializer):
    is_default = serializers.BooleanField(default=True)
