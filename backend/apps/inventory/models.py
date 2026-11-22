"""Inventory models: one stock row per product plus an immutable movement log."""

from django.db import models

from common.models import BaseModel


class StockMovementType(models.TextChoices):
    INITIAL = "initial", "Initial stock"
    PURCHASE = "purchase", "Stock received"
    SALE = "sale", "Sale"
    RETURN = "return", "Customer return"
    ADJUSTMENT = "adjustment", "Manual adjustment"
    DAMAGE = "damage", "Damage / wastage"
    RESERVATION = "reservation", "Reserved for an order"
    RELEASE = "release", "Reservation released"


class Stock(BaseModel):
    """Current available stock for a product.

    One row per product (enforced by a unique FK). All mutations happen inside
    ``apps.inventory.services`` which locks the row with
    ``SELECT ... FOR UPDATE`` before reading or writing ``quantity`` so two
    concurrent checkouts can never oversell the same unit.
    """

    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="stock",
        primary_key=False,
    )
    quantity = models.IntegerField(
        default=0,
        help_text="Physical quantity on hand.",
    )
    reserved_quantity = models.IntegerField(
        default=0,
        help_text="Quantity locked by orders that are not yet fulfilled.",
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Below this value the product is flagged as low stock.",
    )
    track_inventory = models.BooleanField(
        default=True,
        help_text="When false the product is always considered in stock.",
    )

    class Meta(BaseModel.Meta):
        db_table = "inventory_stock"
        verbose_name = "Stock"
        verbose_name_plural = "Stock"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="stock_quantity_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__gte=0),
                name="stock_reserved_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}: {self.quantity} (reserved {self.reserved_quantity})"

    @property
    def quantity_available(self) -> int:
        """Units that can still be sold."""
        if not self.track_inventory:
            return 999_999
        return max(0, self.quantity - self.reserved_quantity)

    @property
    def is_low_stock(self) -> bool:
        return self.track_inventory and self.quantity_available <= self.low_stock_threshold

    @property
    def is_out_of_stock(self) -> bool:
        return self.track_inventory and self.quantity_available <= 0


class InventoryLog(BaseModel):
    """Append-only audit trail of every stock mutation."""

    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="movements"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="stock_movements"
    )
    movement_type = models.CharField(
        max_length=20, choices=StockMovementType.choices, db_index=True
    )
    quantity_change = models.IntegerField(
        help_text="Signed change applied to stock.quantity."
    )
    quantity_before = models.IntegerField()
    quantity_after = models.IntegerField()
    reference = models.CharField(
        max_length=120, blank=True, default="", db_index=True,
        help_text="Order number, adjustment id, etc.",
    )
    reason = models.CharField(max_length=255, blank=True, default="")
    performed_by = models.CharField(max_length=150, blank=True, default="")

    class Meta(BaseModel.Meta):
        db_table = "inventory_log"
        verbose_name = "Inventory log"
        verbose_name_plural = "Inventory logs"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["product", "-created_at"], name="idx_invlog_product_created"),
            models.Index(fields=["movement_type", "-created_at"], name="idx_invlog_type_created"),
        ]

    def __str__(self) -> str:
        return (
            f"{self.get_movement_type_display()} {self.quantity_change:+d} "
            f"-> {self.quantity_after} ({self.product_id})"
        )
