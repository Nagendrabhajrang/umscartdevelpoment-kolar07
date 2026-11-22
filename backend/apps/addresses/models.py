"""Customer delivery addresses."""

from django.db import models

from common.models import BaseModel
from common.validators import normalise_mobile, normalise_pincode, validate_pincode


class AddressLabel(models.TextChoices):
    HOME = "home", "Home"
    WORK = "work", "Work"
    OTHER = "other", "Other"


class Address(BaseModel):
    """A delivery address belonging to a customer.

    Exactly one address per customer may be the default (partial unique index),
    and deleting the current default promotes the most recently used remaining
    address so the customer always has a usable default.
    """

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.CASCADE, related_name="addresses"
    )
    label = models.CharField(
        max_length=20, choices=AddressLabel.choices, default=AddressLabel.HOME
    )
    recipient_name = models.CharField(max_length=150)
    recipient_mobile = models.CharField(max_length=20)

    line1 = models.CharField(max_length=255, help_text="House / flat / building")
    line2 = models.CharField(max_length=255, blank=True, default="", help_text="Street / area")
    landmark = models.CharField(max_length=150, blank=True, default="")
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=100)
    pincode = models.CharField(
        max_length=10, db_index=True, validators=[validate_pincode]
    )
    country = models.CharField(max_length=80, default="India")

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Optional GPS latitude for rider navigation.",
    )
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    is_default = models.BooleanField(default=False, db_index=True)
    delivery_instructions = models.CharField(max_length=255, blank=True, default="")

    class Meta(BaseModel.Meta):
        db_table = "addresses_address"
        verbose_name = "Address"
        verbose_name_plural = "Addresses"
        ordering = ("-is_default", "-updated_at")
        constraints = [
            models.UniqueConstraint(
                fields=["customer"],
                condition=models.Q(is_default=True),
                name="unique_default_address_per_customer",
            ),
            models.CheckConstraint(
                condition=models.Q(latitude__isnull=True)
                | (models.Q(latitude__gte=-90) & models.Q(latitude__lte=90)),
                name="address_latitude_range",
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__isnull=True)
                | (models.Q(longitude__gte=-180) & models.Q(longitude__lte=180)),
                name="address_longitude_range",
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "-is_default"], name="idx_address_customer_default"),
            models.Index(fields=["pincode", "city"], name="idx_address_pincode_city"),
        ]

    def __str__(self) -> str:
        return f"{self.label}: {self.line1}, {self.city} {self.pincode}"

    def save(self, *args, **kwargs):
        # Each field gets its own normaliser: a mobile number also drops
        # dashes and brackets, a pincode only loses whitespace.
        if self.recipient_mobile:
            self.recipient_mobile = normalise_mobile(self.recipient_mobile)
        if self.pincode:
            self.pincode = normalise_pincode(self.pincode)
        super().save(*args, **kwargs)

    @property
    def full_address(self) -> str:
        parts = [
            self.line1,
            self.line2,
            self.landmark,
            self.city,
            self.state,
            self.pincode,
            self.country,
        ]
        return ", ".join(part for part in parts if part)

    @property
    def short_address(self) -> str:
        return f"{self.line1}, {self.city}"

    def get_absolute_url(self):
        return f"/api/v1/addresses/{self.pk}/"
