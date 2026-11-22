"""Catalog API views: categories, products and product images.

SECURITY NOTE: authentication is not implemented in this phase. These
endpoints are unrestricted and must NOT be exposed publicly until the
authentication layer ships. See ``docs/AUTHENTICATION.md``.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.catalog import selectors, services
from apps.catalog.filters import CategoryFilter, ProductFilter
from apps.catalog.serializers import (
    CategorySerializer,
    CategoryWriteSerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    ProductStatusSerializer,
    ProductWriteSerializer,
)
from common.views import BaseModelViewSet


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
class CategoryViewSet(BaseModelViewSet):
    """CRUD API for parent and child categories."""

    filterset_class = CategoryFilter
    search_fields = ("name", "description")
    ordering_fields = ("display_order", "name", "created_at")
    ordering = ("display_order", "name")
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_categories(
            {
                "is_active": _to_bool(params.get("is_active")),
                "parent": params.get("parent"),
                "only_parents": _to_bool(params.get("only_parents")),
                "is_featured": _to_bool(params.get("is_featured")),
                "search": params.get("search"),
            }
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return CategoryWriteSerializer
        return CategorySerializer

    def get_object(self):
        category = services.get_category_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, category)
        # ``product_count`` / ``child_count`` are read-only model properties, so
        # the serializer resolves them itself instead of us assigning here.
        return category

    def create(self, request, *args, **kwargs):
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = services.create_category(**serializer.validated_data)
        return Response(
            CategorySerializer(category, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        category = self.get_object()
        serializer = CategoryWriteSerializer(
            category, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        updated = services.update_category(category, **serializer.validated_data)
        return Response(
            CategorySerializer(updated, context={"request": request}).data
        )

    def destroy(self, request, *args, **kwargs):
        services.delete_category(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Full two-level category tree, optimised for storefront navigation.",
        responses={200: CategorySerializer(many=True)},
        parameters=[OpenApiParameter("include_inactive", bool, required=False)],
    )
    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        include_inactive = _to_bool(request.query_params.get("include_inactive")) or False
        parents = selectors.get_category_tree(include_inactive=include_inactive)
        serializer = CategorySerializer(parents, many=True, context={"request": request})
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
class ProductViewSet(BaseModelViewSet):
    """CRUD API for products."""

    filterset_class = ProductFilter
    search_fields = ("name", "brand", "sku", "barcode", "short_description")
    ordering_fields = (
        "created_at", "name", "selling_price", "mrp", "display_order"
    )
    ordering = ("display_order", "name")
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_products(
            {
                "status": params.get("status"),
                "category": params.get("category"),
                "category_slug": params.get("category_slug"),
                "brand": params.get("brand"),
                "search": params.get("search"),
                "is_featured": _to_bool(params.get("is_featured")),
                "is_vegetarian": _to_bool(params.get("is_vegetarian")),
                "min_price": params.get("min_price"),
                "max_price": params.get("max_price"),
                "in_stock": _to_bool(params.get("in_stock")),
            }
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        if self.action in {"create", "update", "partial_update"}:
            return ProductWriteSerializer
        if self.action == "set_status":
            return ProductStatusSerializer
        return ProductDetailSerializer

    def get_object(self):
        product = services.get_product_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, product)
        return product

    def create(self, request, *args, **kwargs):
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        initial_quantity = request.data.get("initial_quantity", 0)
        try:
            initial_quantity = int(initial_quantity)
        except (TypeError, ValueError):
            initial_quantity = 0
        if initial_quantity < 0:
            initial_quantity = 0

        product = services.create_product(initial_quantity=initial_quantity, **data)
        return Response(
            ProductDetailSerializer(product, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        product = self.get_object()
        serializer = ProductWriteSerializer(product, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = services.update_product(product, **serializer.validated_data)
        return Response(
            ProductDetailSerializer(updated, context={"request": request}).data
        )

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        services.delete_product(product)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=ProductStatusSerializer, responses={200: ProductDetailSerializer}
    )
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        product = self.get_object()
        serializer = ProductStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.set_product_status(product, serializer.validated_data["status"])
        return Response(
            ProductDetailSerializer(updated, context={"request": request}).data
        )

    @extend_schema(
        description="Featured products for the storefront home page.",
        responses={200: ProductListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="featured")
    def featured(self, request):
        limit = _bounded_int(request.query_params.get("limit"), default=10, maximum=50)
        products = selectors.get_featured_products(limit=limit)
        serializer = ProductListSerializer(
            products, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        description="Products from the same category as the given product.",
        responses={200: ProductListSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="related")
    def related(self, request, pk=None):
        product = self.get_object()
        limit = _bounded_int(request.query_params.get("limit"), default=8, maximum=30)
        serializer = ProductListSerializer(
            selectors.get_related_products(product, limit=limit),
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

    @extend_schema(
        request=ProductImageSerializer,
        responses={201: ProductImageSerializer, 200: ProductImageSerializer(many=True)},
        description="List or upload gallery images for a product.",
    )
    @action(detail=True, methods=["get", "post"], url_path="images")
    def images(self, request, pk=None):
        product = self.get_object()
        if request.method == "GET":
            return Response(
                ProductImageSerializer(
                    selectors.list_product_images(product), many=True,
                    context={"request": request},
                ).data
            )

        serializer = ProductImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gallery_image = services.add_product_image(
            product,
            image=serializer.validated_data["image"],
            alt_text=serializer.validated_data.get("alt_text", ""),
            display_order=serializer.validated_data.get("display_order"),
            is_primary=serializer.validated_data.get("is_primary", False),
        )
        return Response(
            ProductImageSerializer(gallery_image, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        description="Delete a gallery image belonging to this product.",
        responses={204: None},
    )
    @action(
        detail=True, methods=["delete"], url_path=r"images/(?P<image_id>[0-9]+)"
    )
    def delete_image(self, request, pk=None, image_id=None):
        product = self.get_object()
        gallery_image = product.images.filter(pk=image_id).first()
        if gallery_image is None:
            return Response(
                {"error": {"code": "not_found", "message": "Image not found.", "status": 404}},
                status=status.HTTP_404_NOT_FOUND,
            )
        services.delete_product_image(gallery_image)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Product images (standalone CRUD)
# ---------------------------------------------------------------------------
class ProductImageViewSet(BaseModelViewSet):
    """Standalone CRUD for product gallery images."""

    filterset_fields = ("product", "is_primary")
    ordering = ("display_order", "id")
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        from apps.catalog.models import ProductImage

        return ProductImage.objects.select_related("product").all()

    def get_serializer_class(self):
        return ProductImageSerializer

    def create(self, request, *args, **kwargs):
        if not request.data.get("product"):
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "'product' is required on this endpoint.",
                        "status": 400,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ProductImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gallery_image = services.add_product_image(
            serializer.validated_data["product"],
            image=serializer.validated_data["image"],
            alt_text=serializer.validated_data.get("alt_text", ""),
            display_order=serializer.validated_data.get("display_order"),
            is_primary=serializer.validated_data.get("is_primary", False),
        )
        return Response(
            ProductImageSerializer(gallery_image, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


def _to_bool(value):
    """Convert query-string values into ``True`` / ``False`` / ``None``."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _bounded_int(value, default, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))
