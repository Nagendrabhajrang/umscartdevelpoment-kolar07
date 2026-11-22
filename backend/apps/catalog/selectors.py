"""Read-only queries for the catalog app."""

from django.db.models import Count, Prefetch, Q, QuerySet

from apps.catalog.models import Category, Product, ProductImage
from common.selectors import id_or_uid_q

PRODUCT_SEARCH_FIELDS = ("name", "brand", "sku", "barcode", "short_description")


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
def list_categories(filters: dict | None = None) -> QuerySet[Category]:
    # NOTE: aliases differ from the model properties ``child_count`` /
    # ``product_count`` on purpose - annotating with the same name would shadow
    # a property that has no setter and raise during iteration.
    queryset = Category.objects.select_related("parent").annotate(
        children_total=Count("children", distinct=True),
        products_total=Count("products", filter=Q(products__is_deleted=False), distinct=True),
    )
    filters = filters or {}

    if filters.get("is_active") is not None:
        queryset = queryset.filter(is_active=filters["is_active"])
    if filters.get("parent") not in (None, ""):
        if str(filters["parent"]).lower() in {"null", "none", "root"}:
            queryset = queryset.filter(parent__isnull=True)
        else:
            queryset = queryset.filter(parent_id=filters["parent"])
    if filters.get("only_parents"):
        queryset = queryset.filter(parent__isnull=True)
    if filters.get("is_featured") is not None:
        queryset = queryset.filter(is_featured=filters["is_featured"])
    search = filters.get("search")
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    return queryset


def get_category_tree(include_inactive: bool = False) -> list[Category]:
    """Return top level categories with children and product counts.

    Optimised with a ``Prefetch`` so the whole tree costs two queries.
    """
    children_qs = Category.objects.select_related("parent").order_by("display_order", "name")
    if not include_inactive:
        children_qs = children_qs.filter(is_active=True)

    parents = (
        Category.objects.filter(parent__isnull=True)
        .select_related("parent")
        .prefetch_related(Prefetch("children", queryset=children_qs))
        .order_by("display_order", "name")
    )
    if not include_inactive:
        parents = parents.filter(is_active=True)
    return list(parents)


def get_category(identifier) -> Category | None:
    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return Category.objects.select_related("parent").filter(query).first()


def get_category_by_slug(slug: str) -> Category | None:
    return Category.objects.select_related("parent").filter(slug=slug).first()


def get_children(category: Category) -> QuerySet[Category]:
    return Category.objects.filter(parent=category)


def get_descendant_ids(category: Category) -> list[int]:
    """Category ids to include when filtering products by a parent category."""
    ids = list(category.children.values_list("id", flat=True))
    return [category.id, *ids]


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
def product_base_queryset() -> QuerySet[Product]:
    return (
        Product.objects.select_related("category", "category__parent", "stock")
        .prefetch_related(
            Prefetch("images", queryset=ProductImage.objects.order_by("display_order", "id"))
        )
    )


def list_products(filters: dict | None = None) -> QuerySet[Product]:
    queryset = product_base_queryset()
    filters = filters or {}

    status_value = filters.get("status")
    if status_value:
        queryset = queryset.filter(status=status_value)

    category = filters.get("category")
    if category:
        category_obj = get_category(category)
        if category_obj:
            queryset = queryset.filter(category_id__in=get_descendant_ids(category_obj))
        else:
            queryset = queryset.none()

    category_slug = filters.get("category_slug")
    if category_slug:
        category_obj = get_category_by_slug(category_slug)
        if category_obj:
            queryset = queryset.filter(category_id__in=get_descendant_ids(category_obj))
        else:
            queryset = queryset.none()

    brand = filters.get("brand")
    if brand:
        queryset = queryset.filter(brand__iexact=brand)

    search = filters.get("search")
    if search:
        query = Q()
        for field in PRODUCT_SEARCH_FIELDS:
            query |= Q(**{f"{field}__icontains": search})
        queryset = queryset.filter(query)

    if filters.get("is_featured") is not None:
        queryset = queryset.filter(is_featured=filters["is_featured"])

    if filters.get("is_vegetarian") is not None:
        queryset = queryset.filter(is_vegetarian=filters["is_vegetarian"])

    min_price = filters.get("min_price")
    if min_price not in (None, ""):
        queryset = queryset.filter(selling_price__gte=min_price)
    max_price = filters.get("max_price")
    if max_price not in (None, ""):
        queryset = queryset.filter(selling_price__lte=max_price)

    if filters.get("in_stock") is True:
        queryset = queryset.filter(stock__quantity__gt=0)
    elif filters.get("in_stock") is False:
        queryset = queryset.filter(Q(stock__isnull=True) | Q(stock__quantity__lte=0))

    return queryset


def get_product(identifier) -> Product | None:
    """Fetch by numeric id, public UUID or SKU."""
    query = id_or_uid_q(identifier)
    queryset = product_base_queryset()
    if query is not None:
        found = queryset.filter(query).first()
        if found:
            return found
    if identifier:
        return queryset.filter(sku__iexact=str(identifier)).first()
    return None


def get_product_by_slug(slug: str) -> Product | None:
    return product_base_queryset().filter(slug=slug).first()


def get_products_by_ids(product_ids) -> QuerySet[Product]:
    return product_base_queryset().filter(id__in=list(product_ids))


def get_featured_products(limit: int = 10) -> QuerySet[Product]:
    return (
        product_base_queryset()
        .filter(status=Product.Status.ACTIVE, is_featured=True)
        .order_by("display_order", "-created_at")[:limit]
    )


def get_related_products(product: Product, limit: int = 8) -> QuerySet[Product]:
    return (
        product_base_queryset()
        .filter(category_id=product.category_id, status=Product.Status.ACTIVE)
        .exclude(pk=product.pk)
        .order_by("-is_featured", "-created_at")[:limit]
    )


def list_product_images(product: Product) -> QuerySet[ProductImage]:
    return product.images.order_by("display_order", "id")


def product_summary() -> dict:
    return Product.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status=Product.Status.ACTIVE)),
        draft=Count("id", filter=Q(status=Product.Status.DRAFT)),
        out_of_stock=Count("id", filter=Q(stock__quantity__lte=0)),
    )
