"""Homepage / promotional banners."""

from django.db import models
from django.utils import timezone

from common.models import BaseModel
from common.validators import validate_image_file


class BannerPlacement(models.TextChoices):
    HERO = "hero", "Hero carousel"
    STRIP = "strip", "Homepage strip"
    CATEGORY = "category", "Category page"
    CART = "cart", "Cart page"
    CHECKOUT = "checkout", "Checkout page"
    POPUP = "popup", "Popup"
    APP = "app", "Mobile app"


class Banner(BaseModel):
    """A clickable image shown in one of the app's placements."""

    title = models.CharField(max_length=150)
    subtitle = models.CharField(max_length=250, blank=True, default="")
    image = models.ImageField(
        upload_to="banners/", validators=[validate_image_file],
        help_text="Desktop image. Recommended 1440x480 for hero banners.",
    )
    mobile_image = models.ImageField(
        upload_to="banners/mobile/", null=True, blank=True,
        validators=[validate_image_file],
    )
    alt_text = models.CharField(max_length=200, blank=True, default="")

    placement = models.CharField(
        max_length=20, choices=BannerPlacement.choices,
        default=BannerPlacement.HERO, db_index=True,
    )
    link_url = models.CharField(
        max_length=500, blank=True, default="",
        help_text="Where the banner navigates. Deep links such as /category/dairy are allowed.",
    )
    link_type = models.CharField(
        max_length=20,
        choices=[
            ("none", "No link"),
            ("url", "URL"),
            ("product", "Product"),
            ("category", "Category"),
            ("coupon", "Coupon"),
        ],
        default="none",
    )
    linked_product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="banners",
    )
    linked_category = models.ForeignKey(
        "catalog.Category", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="banners",
    )
    linked_coupon_code = models.CharField(max_length=40, blank=True, default="")

    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)

    class Meta(BaseModel.Meta):
        db_table = "banners_banner"
        verbose_name = "Banner"
        verbose_name_plural = "Banners"
        ordering = ("display_order", "-created_at")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gt=models.F("start_date")),
                name="banner_end_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(link_type="none")
                | models.Q(link_type="url", link_url__gt="")
                | models.Q(link_type="product", linked_product__isnull=False)
                | models.Q(link_type="category", linked_category__isnull=False)
                | models.Q(link_type="coupon", linked_coupon_code__gt=""),
                name="banner_link_target_consistent",
            ),
        ]
        indexes = [
            models.Index(
                fields=["placement", "is_active", "display_order"],
                name="idx_banner_placement_active",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} [{self.placement}]"

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True

    @property
    def resolved_link(self) -> str:
        """Return the URL the client should navigate to."""
        if self.link_type == "product" and self.linked_product_id:
            return f"/product/{self.linked_product.slug}"
        if self.link_type == "category" and self.linked_category_id:
            return f"/category/{self.linked_category.slug}"
        if self.link_type == "coupon" and self.linked_coupon_code:
            return f"/offers?coupon={self.linked_coupon_code}"
        return self.link_url or ""

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "End date must be after the start date."})
        if self.link_type == "url" and not self.link_url:
            raise ValidationError({"link_url": "A link URL is required for link type 'url'."})
