"""Order models.

Design notes
------------
* **Immutable price snapshots.** :class:`OrderItem` copies the product name,
  SKU, MRP and price at checkout, so editing or discontinuing a product later
  never rewrites history.
* **Address snapshot.** :class:`Order` stores a plain-text copy of the delivery
  address. Editing an address in the address book must not change where an
  already-placed order was delivered.
* **Explicit status transition table.** :func:`allowed_next_statuses` encodes
  the order lifecycle; services refuse illegal jumps.
* **Payment state is derived and stored.** ``payment_status`` is maintained by
  the payments app so order queries never need to join payments.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.addresses.models import AddressLabel
from common.models import BaseModel
from common.utils import round_money, unique_reference

ZERO = Decimal("0.00")


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    PROCESSING = "processing", "Processing"
    PACKED = "packed", "Packed"
    OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"
    RETURNED = "returned", "Returned"
    REFUNDED = "refunded", "Refunded"


class PaymentStatus(models.TextChoices):
    UNPAID = "unpaid", "Unpaid"
    PENDING_VERIFICATION = "pending_verification", "Pending verification"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"
    COD_DUE = "cod_due", "Cash on delivery due"
    COD_COLLECTED = "cod_collected", "Cash collected"


class PaymentMethod(models.TextChoices):
    """Cash on delivery only - UPI was removed from this build.

    The enum keeps the historical ``UPI`` member out deliberately: orders and
    payments only ever accept ``cod`` now, so an accidental "upi" checkout is
    rejected by the serializer instead of creating an unpayable order.
    """

    COD = "cod", "Cash on delivery"


class CancellationReason(models.TextChoices):
    CUSTOMER_REQUEST = "customer_request", "Customer requested"
    OUT_OF_STOCK = "out_of_stock", "Out of stock"
    PAYMENT_FAILED = "payment_failed", "Payment failed / not verified"
    STORE_CLOSED = "store_closed", "Store closed"
    ADDRESS_ISSUE = "address_issue", "Delivery address issue"
    OTHER = "other", "Other"


#: Legal order status transitions.
ALLOWED_TRANSITIONS = {
    OrderStatus.PENDING: {
        OrderStatus.CONFIRMED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.CONFIRMED: {
        OrderStatus.PROCESSING,
        OrderStatus.CANCELLED,
    },
    OrderStatus.PROCESSING: {
        OrderStatus.PACKED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.PACKED: {
        OrderStatus.OUT_FOR_DELIVERY,
        OrderStatus.CANCELLED,
    },
    OrderStatus.OUT_FOR_DELIVERY: {
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.DELIVERED: {
        OrderStatus.RETURNED,
    },
    OrderStatus.RETURNED: {
        OrderStatus.REFUNDED,
    },
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
}

#: Statuses that still hold a claim on inventory.
ACTIVE_ORDER_STATUSES = (
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.PROCESSING,
    OrderStatus.PACKED,
    OrderStatus.OUT_FOR_DELIVERY,
)

#: Statuses that count as realised revenue.
REVENUE_ORDER_STATUSES = (
    OrderStatus.CONFIRMED,
    OrderStatus.PROCESSING,
    OrderStatus.PACKED,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
)


def allowed_next_statuses(current: str) -> set[str]:
    return ALLOWED_TRANSITIONS.get(current, set())


class Order(BaseModel):
    """A placed customer order."""

    order_number = models.CharField(
        max_length=40, unique=True, db_index=True, editable=False
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    address = models.ForeignKey(
        "addresses.Address",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        help_text="Live address record (may be deleted by the customer later).",
    )

    # --- Address snapshot (authoritative for this order) -------------------
    delivery_recipient_name = models.CharField(max_length=150)
    delivery_recipient_mobile = models.CharField(max_length=20)
    delivery_address_line1 = models.CharField(max_length=255)
    delivery_address_line2 = models.CharField(max_length=255, blank=True, default="")
    delivery_landmark = models.CharField(max_length=150, blank=True, default="")
    delivery_city = models.CharField(max_length=100)
    delivery_state = models.CharField(max_length=100)
    delivery_pincode = models.CharField(max_length=10)
    delivery_country = models.CharField(max_length=80, default="India")
    delivery_label = models.CharField(
        max_length=20, choices=AddressLabel.choices, default=AddressLabel.HOME
    )
    delivery_instructions = models.CharField(max_length=255, blank=True, default="")

    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING,
        db_index=True,
    )
    payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, db_index=True
    )
    payment_status = models.CharField(
        max_length=25, choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID, db_index=True,
    )

    # --- Money (all snapshotted at checkout) ------------------------------
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    mrp_total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    product_savings = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    coupon_code = models.CharField(max_length=40, blank=True, default="")
    promotion_name = models.CharField(max_length=150, blank=True, default="")
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    packaging_charge = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    grand_total = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(ZERO)]
    )
    currency = models.CharField(max_length=3, default="INR")

    item_count = models.PositiveIntegerField(default=0)
    total_quantity = models.PositiveIntegerField(default=0)

    customer_notes = models.TextField(blank=True, default="")
    internal_notes = models.TextField(blank=True, default="")
    delivery_eta_minutes = models.PositiveIntegerField(default=0)

    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(
        max_length=30, choices=CancellationReason.choices, blank=True, default=""
    )
    cancellation_note = models.CharField(max_length=255, blank=True, default="")

    class Meta(BaseModel.Meta):
        db_table = "orders_order"
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(grand_total__gte=0), name="order_grand_total_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0), name="order_subtotal_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="order_discount_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(delivery_charge__gte=0),
                name="order_delivery_charge_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "status"], name="idx_order_customer_status"),
            models.Index(fields=["status", "-created_at"], name="idx_order_status_created"),
            models.Index(fields=["payment_status", "payment_method"], name="idx_order_payment"),
            models.Index(fields=["-created_at"], name="idx_order_created_desc"),
        ]

    def __str__(self) -> str:
        return f"{self.order_number} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._build_order_number()
        super().save(*args, **kwargs)

    def _build_order_number(self) -> str:
        from apps.store_settings.models import StoreSettings

        try:
            prefix = StoreSettings.load().order_prefix or "UMS"
        except Exception:  # pragma: no cover - settings table may not exist yet
            prefix = "UMS"
        return unique_reference(Order, "order_number", prefix.upper(), length=6)

    # --- derived properties ------------------------------------------------
    @property
    def next_statuses(self) -> list[str]:
        return sorted(allowed_next_statuses(self.status))

    @property
    def can_be_cancelled(self) -> bool:
        return OrderStatus.CANCELLED in allowed_next_statuses(self.status)

    @property
    def is_final(self) -> bool:
        return self.status in {
            OrderStatus.DELIVERED,
            OrderStatus.CANCELLED,
            OrderStatus.RETURNED,
            OrderStatus.REFUNDED,
        }

    @property
    def is_paid(self) -> bool:
        return self.payment_status in {
            PaymentStatus.PAID,
            PaymentStatus.COD_COLLECTED,
        }

    @property
    def total_savings(self) -> Decimal:
        return round_money(self.product_savings + self.discount_amount)

    @property
    def full_delivery_address(self) -> str:
        parts = [
            self.delivery_address_line1,
            self.delivery_address_line2,
            self.delivery_landmark,
            self.delivery_city,
            self.delivery_state,
            self.delivery_pincode,
            self.delivery_country,
        ]
        return ", ".join(part for part in parts if part)

    def get_absolute_url(self):
        return f"/api/v1/orders/{self.pk}/"


class OrderItem(BaseModel):
    """A single product line inside an order (immutable snapshot)."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    product_name = models.CharField(max_length=200)
    product_sku = models.CharField(max_length=64)
    unit_label = models.CharField(max_length=60, blank=True, default="")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_mrp = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    line_savings = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    product_image = models.ImageField(
        upload_to="orders/items/", null=True, blank=True,
        help_text="Snapshot of the product image at purchase time.",
    )

    class Meta(BaseModel.Meta):
        db_table = "orders_order_item"
        verbose_name = "Order item"
        verbose_name_plural = "Order items"
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="order_item_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(line_total__gte=0), name="order_item_total_non_negative"
            ),
            models.UniqueConstraint(
                fields=["order", "product"], name="unique_product_per_order"
            ),
        ]
        indexes = [
            models.Index(fields=["order", "product"], name="idx_orderitem_order_product"),
            models.Index(fields=["product"], name="idx_orderitem_product"),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.product_name}"


class OrderStatusHistory(BaseModel):
    """Audit trail of every order status change."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="status_history"
    )
    from_status = models.CharField(
        max_length=20, choices=OrderStatus.choices, blank=True, default=""
    )
    to_status = models.CharField(max_length=20, choices=OrderStatus.choices)
    note = models.CharField(max_length=255, blank=True, default="")
    changed_by = models.CharField(
        max_length=150, blank=True, default="system",
        help_text="Free text actor; links to an admin user once auth exists.",
    )

    class Meta(BaseModel.Meta):
        db_table = "orders_status_history"
        verbose_name = "Order status history"
        verbose_name_plural = "Order status history"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["order", "-created_at"], name="idx_orderhistory_order"),
        ]

    def __str__(self) -> str:
        return f"{self.order_id}: {self.from_status or '-'} -> {self.to_status}"
