"""Customer domain models."""

from django.core.validators import EmailValidator
from django.db import models

from common.models import BaseModel, SoftDeleteModel
from common.validators import normalise_mobile, validate_mobile_number


class CustomerStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    BLOCKED = "blocked", "Blocked"


class Customer(BaseModel, SoftDeleteModel):
    """A shopper on UMS Mart.

    In this phase a customer is created directly by the API (no OTP workflow
    yet). ``mobile_number`` is the natural business key and is unique.
    """

    full_name = models.CharField(max_length=150, db_index=True)
    mobile_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        validators=[validate_mobile_number],
        help_text="Primary business identifier. Unique across the platform.",
    )
    email = models.EmailField(
        max_length=254,
        unique=True,
        null=True,
        blank=True,
        validators=[EmailValidator()],
    )
    status = models.CharField(
        max_length=20,
        choices=CustomerStatus.choices,
        default=CustomerStatus.ACTIVE,
        db_index=True,
    )
    is_mobile_verified = models.BooleanField(
        default=False,
        help_text="Will be set by the future OTP authentication flow.",
    )
    notes = models.TextField(blank=True, default="")
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = "customers_customer"
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(mobile_number__regex=r"^\+?[1-9]\d{7,14}$"),
                name="customer_mobile_format",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="idx_customer_status_created"),
            models.Index(fields=["full_name"], name="idx_customer_full_name"),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.mobile_number})"

    def save(self, *args, **kwargs):
        # Normalise the mobile number so "+91 98765-43210" and "+919876543210"
        # cannot create two different customers for the same person.
        if self.mobile_number:
            self.mobile_number = normalise_mobile(self.mobile_number)
        if self.email:
            self.email = self.email.strip().lower() or None
        super().save(*args, **kwargs)

    @property
    def can_order(self) -> bool:
        return self.status == CustomerStatus.ACTIVE

    @property
    def default_address(self):
        """The customer's default delivery address (Address has no soft delete)."""
        return self.addresses.filter(is_default=True).first()

    @property
    def address_count(self) -> int:
        return self.addresses.count()

    @property
    def order_count(self) -> int:
        return self.orders.count()

    @property
    def lifetime_value(self):
        from decimal import Decimal

        from apps.orders.models import OrderStatus

        total = self.orders.filter(
            status__in=[
                OrderStatus.PACKED,
                OrderStatus.OUT_FOR_DELIVERY,
                OrderStatus.DELIVERED,
            ]
        ).aggregate(total=models.Sum("grand_total"))["total"]
        return total or Decimal("0.00")


class CustomerNote(BaseModel):
    """Audit trail of internal notes written against a customer."""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="internal_notes",
    )
    note = models.TextField()
    author = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="Free-text author; will link to an admin user once auth exists.",
    )

    class Meta(BaseModel.Meta):
        db_table = "customers_customer_note"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Note for {self.customer_id} ({self.created_at:%Y-%m-%d})"
