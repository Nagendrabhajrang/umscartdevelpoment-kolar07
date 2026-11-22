"""Store configuration: delivery charges, minimum order value, tax defaults.

A single ``StoreSettings`` row (singleton) holds the live configuration, while
:class:`DeliverySlab` rows describe graduated delivery charges based on the
cart subtotal. Keeping this in the database rather than in settings.py means
store staff can change delivery rules without a redeploy.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from common.models import BaseModel
from common.utils import round_money


class StoreSettings(BaseModel):
    """Singleton store configuration (pk is always 1)."""

    store_name = models.CharField(max_length=150, default="UMS Mart")
    tagline = models.CharField(max_length=200, blank=True, default="")
    contact_phone = models.CharField(max_length=20, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")

    currency_code = models.CharField(max_length=3, default="INR")
    currency_symbol = models.CharField(max_length=5, default="₹")

    # --- Delivery ---------------------------------------------------------
    delivery_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("40.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Flat delivery charge applied when no slab matches.",
    )
    free_delivery_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("500.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Cart subtotal at or above which delivery is free.",
    )
    minimum_order_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("99.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Below this cart value checkout is refused.",
    )
    max_delivery_distance_km = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("15.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    delivery_eta_minutes = models.PositiveIntegerField(default=45)

    # --- Taxes & fees -----------------------------------------------------
    default_tax_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    packaging_charge = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    apply_tax_on_delivery = models.BooleanField(default=False)

    # --- Order rules ------------------------------------------------------
    cod_enabled = models.BooleanField(default=True)
    upi_enabled = models.BooleanField(default=True)
    max_items_per_order = models.PositiveIntegerField(default=50)
    order_prefix = models.CharField(max_length=10, default="UMS")
    auto_cancel_unpaid_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Unpaid UPI orders are cancelled after this many minutes.",
    )

    upi_id = models.CharField(max_length=120, blank=True, default="")
    upi_payee_name = models.CharField(max_length=150, blank=True, default="")
    upi_qr_image = models.ImageField(
        upload_to="store/upi/", null=True, blank=True
    )
    cod_instructions = models.TextField(blank=True, default="")

    is_store_open = models.BooleanField(
        default=True, help_text="When false, checkout is blocked store-wide."
    )
    maintenance_message = models.TextField(blank=True, default="")

    class Meta(BaseModel.Meta):
        db_table = "store_settings_store"
        verbose_name = "Store settings"
        verbose_name_plural = "Store settings"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pk=1), name="store_settings_singleton"
            ),
            models.CheckConstraint(
                condition=models.Q(delivery_charge__gte=0),
                name="store_delivery_charge_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_order_value__gte=0),
                name="store_min_order_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(free_delivery_threshold__gte=0),
                name="store_free_delivery_threshold_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.store_name

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce the singleton
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "StoreSettings":
        """Return the singleton row, creating it with defaults if missing."""
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


class DeliverySlab(BaseModel):
    """Graduated delivery charge for a cart subtotal range.

    Evaluation order: the slab with the highest ``min_order_value`` that is
    ``<= subtotal`` wins, so overlapping ranges resolve deterministically.
    ``max_order_value = None`` means "and above".
    """

    name = models.CharField(max_length=100)
    min_order_value = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    max_order_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    delivery_charge = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta(BaseModel.Meta):
        db_table = "store_settings_delivery_slab"
        verbose_name = "Delivery slab"
        verbose_name_plural = "Delivery slabs"
        ordering = ("min_order_value",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_order_value__gte=0),
                name="slab_min_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(max_order_value__isnull=True)
                | models.Q(max_order_value__gt=models.F("min_order_value")),
                name="slab_max_above_min",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active", "min_order_value"], name="idx_slab_active_min"),
        ]

    def __str__(self) -> str:
        upper = f"{self.max_order_value}" if self.max_order_value is not None else "+"
        return f"{self.name}: {self.min_order_value} - {upper} => {self.delivery_charge}"

    def applies_to(self, subtotal) -> bool:
        subtotal = Decimal(str(subtotal or 0))
        if subtotal < self.min_order_value:
            return False
        if self.max_order_value is not None and subtotal > self.max_order_value:
            return False
        return True

    @property
    def is_free(self) -> bool:
        return round_money(self.delivery_charge) == Decimal("0.00")


class StoreHoliday(BaseModel):
    """Dates on which the store does not deliver."""

    date = models.DateField(unique=True, db_index=True)
    reason = models.CharField(max_length=200, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        db_table = "store_settings_holiday"
        verbose_name = "Store holiday"
        verbose_name_plural = "Store holidays"
        ordering = ("date",)

    def __str__(self) -> str:
        return f"{self.date} - {self.reason or 'Holiday'}"
