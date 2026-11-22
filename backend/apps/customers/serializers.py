"""Serializers for the customers app."""

from rest_framework import serializers

from apps.customers.models import Customer, CustomerNote, CustomerStatus
from common.validators import normalise_mobile, validate_mobile_number


class CustomerListSerializer(serializers.ModelSerializer):
    order_count = serializers.IntegerField(source="orders_total", read_only=True)
    address_count = serializers.IntegerField(source="addresses_total", read_only=True)

    class Meta:
        model = Customer
        fields = (
            "id",
            "uid",
            "full_name",
            "mobile_number",
            "email",
            "status",
            "is_mobile_verified",
            "order_count",
            "address_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CustomerDetailSerializer(serializers.ModelSerializer):
    address_count = serializers.IntegerField(read_only=True)
    order_count = serializers.IntegerField(read_only=True)
    lifetime_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = Customer
        fields = (
            "id",
            "uid",
            "full_name",
            "mobile_number",
            "email",
            "status",
            "is_mobile_verified",
            "notes",
            "address_count",
            "order_count",
            "lifetime_value",
            "last_login_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "uid",
            "address_count",
            "order_count",
            "lifetime_value",
            "last_login_at",
            "created_at",
            "updated_at",
        )


class CustomerWriteSerializer(serializers.ModelSerializer):
    """Create / update serializer with business-level duplicate checks."""

    mobile_number = serializers.CharField(
        max_length=20, validators=[validate_mobile_number]
    )

    class Meta:
        model = Customer
        fields = (
            "full_name",
            "mobile_number",
            "email",
            "status",
            "is_mobile_verified",
            "notes",
        )
        # The model marks mobile_number/email unique, which makes DRF attach
        # UniqueValidators that return 400 before our validators run. Drop them
        # so duplicates surface as a meaningful 409 Conflict instead.
        extra_kwargs = {
            "mobile_number": {"validators": []},
            "email": {"validators": []},
        }

    def validate_full_name(self, value):
        value = (value or "").strip()
        if len(value) < 2:
            raise serializers.ValidationError("Full name must be at least 2 characters.")
        return value

    def validate_mobile_number(self, value):
        value = normalise_mobile(value)
        queryset = Customer.all_objects.filter(mobile_number=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            # 409 Conflict, matching the service layer's duplicate handling.
            from common.exceptions import ConflictError

            raise ConflictError(
                message="A customer with this mobile number already exists.",
                code="duplicate_mobile_number",
                details={"mobile_number": value},
            )
        return value

    def validate_email(self, value):
        if not value:
            return None
        value = value.strip().lower()
        queryset = Customer.all_objects.filter(email=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            from common.exceptions import ConflictError

            raise ConflictError(
                message="A customer with this email address already exists.",
                code="duplicate_email",
                details={"email": value},
            )
        return value


class CustomerStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=CustomerStatus.choices)


class CustomerNoteSerializer(serializers.ModelSerializer):
    # The customer comes from the URL, so the client never supplies it.
    customer = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = CustomerNote
        fields = ("id", "uid", "customer", "note", "author", "created_at", "updated_at")
        read_only_fields = ("id", "uid", "customer", "created_at", "updated_at")


class CustomerSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    blocked = serializers.IntegerField()
    inactive = serializers.IntegerField()
