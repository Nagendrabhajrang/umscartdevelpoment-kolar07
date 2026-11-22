"""Catalog domain models: categories, products and product images.

Category hierarchy is two levels by design (parent category -> child
category), which matches how grocery storefronts are navigated and keeps the
tree shallow enough to prefetch efficiently. A self-referencing FK allows more
depth later without a schema migration if the business needs it.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

from common.models import BaseModel, SoftDeleteModel
from common.utils import percent_discount
from common.validators import validate_image_file


class UnitType(models.TextChoices):
    PIECE = "piece", "Piece"
    GRAM = "gram", "Gram"
    KILOGRAM = "kg", "Kilogram"
    MILLILITRE = "ml", "Millilitre"
    LITRE = "litre", "Litre"
    PACK = "pack", "Pack"
    DOZEN = "dozen", "Dozen"
    BUNCH = "bunch", "Bunch"


class Category(BaseModel):
    """A product category. Parent categories group child categories."""

    name = models.CharField(max_length=150, db_index=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
        help_text="Leave empty for a top-level (parent) category.",
    )
    description = models.TextField(blank=True, default="")
    image = models.ImageField(
        upload_to="catalog/categories/", null=True, blank=True,
        validators=[validate_image_file],
    )
    icon_name = models.CharField(
        max_length=60, blank=True, default="",
        help_text="Icon identifier for the React/Flutter clients.",
    )
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta(BaseModel.Meta):
        db_table = "catalog_category"
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ("display_order", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"], name="unique_category_name_per_parent"
            ),
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("id")),
                name="category_cannot_be_own_parent",
            ),
        ]
        indexes = [
            models.Index(fields=["parent", "is_active"], name="idx_category_parent_active"),
            models.Index(fields=["is_featured", "display_order"], name="idx_category_featured"),
        ]

    def __str__(self) -> str:
        return f"{self.parent.name} > {self.name}" if self.parent_id else self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from common.utils import unique_slug

            self.slug = unique_slug(Category, self.name)
        super().save(*args, **kwargs)

    @property
    def is_parent(self) -> bool:
        return self.parent_id is None

    @property
    def full_path(self) -> str:
        return str(self)

    @property
    def product_count(self) -> int:
        return self.products.filter(is_deleted=False).count()

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError({"parent": "A category cannot be its own parent."})
        # Guard against deeper-than-two-level trees via the parent's parent.
        if self.parent_id and self.parent and self.parent.parent_id:
            raise ValidationError(
                {"parent": "Categories support a maximum depth of two levels."}
            )


class Product(BaseModel, SoftDeleteModel):
    """A sellable grocery item.

    Products are *soft* deleted: history-bearing order items keep their FK, but
    the product disappears from the storefront. ``Product.objects`` hides
    deleted rows; ``Product.all_objects`` includes them (used by admin/checks).
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        DISCONTINUED = "discontinued", "Discontinued"

    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    sku = models.CharField(
        max_length=64, unique=True, db_index=True,
        help_text="Stock keeping unit. Auto-generated when omitted.",
    )
    barcode = models.CharField(max_length=64, blank=True, default="", db_index=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        help_text="Child category (or parent category for flat catalogs).",
    )
    brand = models.CharField(max_length=120, blank=True, default="", db_index=True)
    description = models.TextField(blank=True, default="")
    short_description = models.CharField(max_length=300, blank=True, default="")

    unit_type = models.CharField(
        max_length=20, choices=UnitType.choices, default=UnitType.PIECE
    )
    unit_value = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Quantity in the chosen unit, e.g. 500 for '500 gram'.",
    )

    mrp = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Maximum retail price (strike-through price).",
    )
    selling_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    image = models.ImageField(
        upload_to="catalog/products/", null=True, blank=True,
        validators=[validate_image_file],
    )
    is_vegetarian = models.BooleanField(default=True)
    tax_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    max_order_quantity = models.PositiveIntegerField(
        default=20, help_text="Per-order cap to prevent abuse."
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    is_featured = models.BooleanField(default=False, db_index=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta(BaseModel.Meta):
        db_table = "catalog_product"
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ("display_order", "name")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(selling_price__gte=0), name="product_price_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(mrp__gte=models.F("selling_price")),
                name="product_selling_price_not_above_mrp",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_value__gt=0), name="product_unit_value_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(max_order_quantity__gte=1),
                name="product_max_order_quantity_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["category", "status"], name="idx_product_category_status"),
            models.Index(fields=["status", "is_featured"], name="idx_product_status_featured"),
            models.Index(fields=["brand", "status"], name="idx_product_brand_status"),
            models.Index(fields=["-created_at"], name="idx_product_created_desc"),
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.sku}]"

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = self._generate_sku()
        if not self.slug:
            from common.utils import unique_slug

            self.slug = unique_slug(Product, self.name, max_length=200)
        super().save(*args, **kwargs)

    def _generate_sku(self) -> str:
        from common.utils import generate_reference

        return generate_reference("SKU", length=8)

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.mrp is not None and self.selling_price is not None:
            if self.selling_price > self.mrp:
                raise ValidationError(
                    {"selling_price": "Selling price cannot be greater than MRP."}
                )

    @property
    def unit_label(self) -> str:
        unit = self.get_unit_type_display()
        value = f"{self.unit_value.normalize():f}"
        return f"{value} {unit.lower()}"

    @property
    def discount_percent(self) -> Decimal:
        return percent_discount(self.mrp, self.selling_price)

    @property
    def discount_amount(self) -> Decimal:
        return max(Decimal("0.00"), self.mrp - self.selling_price)

    @property
    def in_stock(self) -> bool:
        stock = getattr(self, "stock", None)
        return bool(stock and stock.quantity_available > 0)

    @property
    def available_quantity(self) -> int:
        stock = getattr(self, "stock", None)
        return stock.quantity_available if stock else 0

    @property
    def is_purchasable(self) -> bool:
        return self.status == self.Status.ACTIVE and self.available_quantity > 0

    def get_absolute_url(self):
        return reverse("v1:catalog:product-detail", kwargs={"pk": self.pk})


class ProductImage(BaseModel):
    """Additional gallery images for a product."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(
        upload_to="catalog/products/gallery/", validators=[validate_image_file]
    )
    alt_text = models.CharField(max_length=200, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta(BaseModel.Meta):
        db_table = "catalog_product_image"
        verbose_name = "Product image"
        verbose_name_plural = "Product images"
        ordering = ("display_order", "id")
        indexes = [
            models.Index(fields=["product", "display_order"], name="idx_productimage_order"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(is_primary=True),
                name="unique_primary_image_per_product",
            )
        ]

    def __str__(self) -> str:
        return f"Image {self.pk} for product {self.product_id}"
