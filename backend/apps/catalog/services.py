"""Business logic for categories, products and product images."""

import logging

from django.db import IntegrityError, transaction

from apps.catalog.models import Category, Product, ProductImage
from common.exceptions import (
    BusinessRuleError,
    ConflictError,
    ResourceNotFoundError,
)
from common.utils import unique_slug

logger = logging.getLogger("apps.catalog")


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
@transaction.atomic
def create_category(*, name, parent=None, description="", icon_name="",
                    display_order=0, is_active=True, is_featured=False, image=None,
                    slug=None) -> Category:
    if parent and parent.parent_id is not None:
        raise BusinessRuleError(
            message="Categories support a maximum depth of two levels "
                    "(parent category -> child category).",
            code="category_depth_exceeded",
        )
    if Category.objects.filter(parent=parent, name__iexact=name.strip()).exists():
        raise ConflictError(
            message="A category with this name already exists under the same parent.",
            code="duplicate_category",
            details={"name": name, "parent": parent.id if parent else None},
        )

    category = Category(
        name=name.strip(),
        parent=parent,
        description=description or "",
        icon_name=icon_name or "",
        display_order=display_order,
        is_active=is_active,
        is_featured=is_featured,
        image=image,
        slug=slug or unique_slug(Category, name),
    )
    category.full_clean(exclude=["uid", "created_at", "updated_at"])
    try:
        category.save()
    except IntegrityError as exc:
        raise ConflictError(
            message="A category with this name/slug already exists.",
            code="duplicate_category",
        ) from exc
    logger.info("Category created id=%s name=%s", category.id, category.name)
    return category


@transaction.atomic
def update_category(category: Category, **data) -> Category:
    parent = data.pop("parent", None)
    if "parent" in data or parent is not None:
        if parent is not None:
            if parent.pk == category.pk:
                raise BusinessRuleError(
                    message="A category cannot be its own parent.",
                    code="invalid_category_parent",
                )
            if parent.parent_id is not None:
                raise BusinessRuleError(
                    message="Categories support a maximum depth of two levels.",
                    code="category_depth_exceeded",
                )
            if category.children.exists():
                raise BusinessRuleError(
                    message="A parent category with children cannot be nested "
                            "under another category.",
                    code="category_has_children",
                )
        category.parent = parent

    for field, value in data.items():
        setattr(category, field, value)
    if "name" in data and not category.slug:
        category.slug = unique_slug(Category, category.name)

    category.full_clean(exclude=["uid", "created_at", "updated_at"])
    category.save()
    logger.info("Category updated id=%s", category.id)
    return category


@transaction.atomic
def delete_category(category: Category) -> None:
    if category.children.exists():
        raise BusinessRuleError(
            message="This category has sub-categories. Delete or move them first.",
            code="category_has_children",
            status_code=409,
        )
    # ``category.products`` hides soft-deleted products, but they still hold a
    # PROTECT foreign key, so the raw manager must be consulted.
    if Product.all_objects.filter(category_id=category.id).exists():
        raise BusinessRuleError(
            message=(
                "This category still contains products (including archived ones). "
                "Reassign or permanently remove them first."
            ),
            code="category_has_products",
            status_code=409,
        )
    category_id = category.id
    category.delete()
    logger.info("Category deleted id=%s", category_id)


def get_category_or_404(identifier) -> Category:
    from apps.catalog.selectors import get_category

    category = get_category(identifier)
    if category is None:
        raise ResourceNotFoundError(
            message=f"Category '{identifier}' was not found.", code="category_not_found"
        )
    return category


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
@transaction.atomic
def create_product(*, name, category, mrp, selling_price, sku=None, barcode="",
                   brand="", description="", short_description="", unit_type="piece",
                   unit_value=1, image=None, is_vegetarian=True, tax_percent=0,
                   max_order_quantity=20, status="active", is_featured=False,
                   display_order=0, slug=None, initial_quantity=0) -> Product:
    from apps.inventory.services import set_initial_stock

    if selling_price > mrp:
        raise BusinessRuleError(
            message="Selling price cannot be greater than MRP.",
            code="invalid_price",
            details={"mrp": str(mrp), "selling_price": str(selling_price)},
        )
    if sku and Product.all_objects.filter(sku__iexact=sku).exists():
        raise ConflictError(
            message="A product with this SKU already exists.",
            code="duplicate_sku",
            details={"sku": sku},
        )

    product = Product(
        name=name.strip(),
        category=category,
        mrp=mrp,
        selling_price=selling_price,
        sku=sku or "",
        barcode=barcode or "",
        brand=brand or "",
        description=description or "",
        short_description=short_description or "",
        unit_type=unit_type,
        unit_value=unit_value,
        image=image,
        is_vegetarian=is_vegetarian,
        tax_percent=tax_percent,
        max_order_quantity=max_order_quantity,
        status=status,
        is_featured=is_featured,
        display_order=display_order,
        slug=slug or unique_slug(Product, name, max_length=200),
    )
    if not product.sku:
        product.sku = product._generate_sku()
    product.full_clean(exclude=["uid", "created_at", "updated_at"])
    try:
        product.save()
    except IntegrityError as exc:
        raise ConflictError(
            message="A product with this name/slug/SKU already exists.",
            code="duplicate_product",
        ) from exc

    # Every product gets its inventory row immediately so stock lookups never
    # need to handle a missing relation.
    set_initial_stock(product, quantity=initial_quantity or 0)

    logger.info("Product created id=%s sku=%s", product.id, product.sku)
    return product


@transaction.atomic
def update_product(product: Product, **data) -> Product:
    mrp = data.get("mrp", product.mrp)
    selling_price = data.get("selling_price", product.selling_price)
    if selling_price > mrp:
        raise BusinessRuleError(
            message="Selling price cannot be greater than MRP.",
            code="invalid_price",
            details={"mrp": str(mrp), "selling_price": str(selling_price)},
        )

    new_sku = data.get("sku")
    if new_sku and new_sku.lower() != product.sku.lower():
        if Product.all_objects.filter(sku__iexact=new_sku).exclude(pk=product.pk).exists():
            raise ConflictError(
                message="A product with this SKU already exists.",
                code="duplicate_sku",
                details={"sku": new_sku},
            )

    for field, value in data.items():
        setattr(product, field, value)
    product.full_clean(exclude=["uid", "created_at", "updated_at"])
    product.save()
    logger.info("Product updated id=%s fields=%s", product.id, sorted(data))
    return product


@transaction.atomic
def delete_product(product: Product) -> None:
    """Soft-delete a product.

    Products are never hard deleted because historical order items reference
    them; the soft delete hides them from the storefront while keeping order
    history intact.
    """
    product.delete()
    logger.info("Product soft-deleted id=%s sku=%s", product.id, product.sku)


@transaction.atomic
def set_product_status(product: Product, status: str) -> Product:
    valid = {choice for choice, _ in Product.Status.choices}
    if status not in valid:
        raise BusinessRuleError(
            message=f"Invalid product status '{status}'.",
            code="invalid_status",
            details={"allowed": sorted(valid)},
        )
    product.status = status
    product.save(update_fields=["status", "updated_at"])
    return product


def get_product_or_404(identifier) -> Product:
    from apps.catalog.selectors import get_product

    product = get_product(identifier)
    if product is None:
        raise ResourceNotFoundError(
            message=f"Product '{identifier}' was not found.", code="product_not_found"
        )
    return product


# ---------------------------------------------------------------------------
# Product images
# ---------------------------------------------------------------------------
@transaction.atomic
def add_product_image(product: Product, *, image, alt_text="", display_order=None,
                      is_primary=False) -> ProductImage:
    if is_primary:
        product.images.filter(is_primary=True).update(is_primary=False)
    if display_order is None:
        last = product.images.order_by("-display_order").first()
        display_order = (last.display_order + 1) if last else 0

    gallery_image = ProductImage.objects.create(
        product=product,
        image=image,
        alt_text=alt_text or "",
        display_order=display_order,
        is_primary=is_primary,
    )
    logger.info("Product image added product=%s image=%s", product.id, gallery_image.id)
    return gallery_image


@transaction.atomic
def update_product_image(gallery_image: ProductImage, **data) -> ProductImage:
    if data.get("is_primary"):
        gallery_image.product.images.exclude(pk=gallery_image.pk).update(is_primary=False)
    for field, value in data.items():
        setattr(gallery_image, field, value)
    gallery_image.save()
    return gallery_image


@transaction.atomic
def delete_product_image(gallery_image: ProductImage) -> None:
    gallery_image.delete()
