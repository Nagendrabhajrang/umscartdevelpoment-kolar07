"""Wishlist (favourites)."""

from django.db import models

from common.models import BaseModel


class Wishlist(BaseModel):
    """A named collection of favourite products.

    Every customer gets a ``Default`` wishlist automatically; additional named
    lists ("Diwali shopping") are supported without a schema change.
    """

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.CASCADE, related_name="wishlists"
    )
    name = models.CharField(max_length=120, default="Default")
    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)

    class Meta(BaseModel.Meta):
        db_table = "wishlist_wishlist"
        verbose_name = "Wishlist"
        verbose_name_plural = "Wishlists"
        ordering = ("-is_default", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "name"], name="unique_wishlist_name_per_customer"
            ),
            models.UniqueConstraint(
                fields=["customer"],
                condition=models.Q(is_default=True),
                name="unique_default_wishlist_per_customer",
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "is_default"], name="idx_wishlist_customer_default"),
        ]

    def __str__(self) -> str:
        return f"{self.customer_id}: {self.name}"

    @property
    def item_count(self) -> int:
        return self.items.count()


class WishlistItem(BaseModel):
    """A product saved to a wishlist."""

    wishlist = models.ForeignKey(
        Wishlist, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="wishlist_items"
    )
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta(BaseModel.Meta):
        db_table = "wishlist_item"
        verbose_name = "Wishlist item"
        verbose_name_plural = "Wishlist items"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["wishlist", "product"], name="unique_wishlist_product"
            ),
        ]
        indexes = [
            models.Index(fields=["wishlist", "-created_at"], name="idx_wishlistitem_created"),
        ]

    def __str__(self) -> str:
        return f"{self.wishlist_id} -> product {self.product_id}"
