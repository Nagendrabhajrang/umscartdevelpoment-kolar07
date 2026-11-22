"""Serializers for the catalog app."""

from rest_framework import serializers

from apps.catalog.models import Category, Product, ProductImage, UnitType
from common.validators import validate_image_file


class RelativeImageField(serializers.ImageField):
    """An image field that prints a relative path (/media/...).

    The stock field prints an absolute URL built from the request host
    (http://127.0.0.1:8000/media/...). Behind the storefront proxy or a preview
    domain the browser cannot reach that host, so category pictures never
    loaded. Products and banners already return relative paths; this does the
    same for categories. Uploads work exactly as before.
    """

    def to_representation(self, value):
        if not value:
            return None
        try:
            return value.url
        except ValueError:
            return None


class CategoryChildSerializer(serializers.ModelSerializer):
    image = RelativeImageField(read_only=True)
    product_count = serializers.SerializerMethodField()
    child_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id", "uid", "name", "slug", "description", "image", "icon_name",
            "display_order", "is_featured", "is_active", "product_count",
            "child_count", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_product_count(self, obj) -> int:
        return getattr(obj, "products_total", obj.product_count)

    def get_child_count(self, obj) -> int:
        return getattr(obj, "children_total", obj.children.count())


class CategorySerializer(serializers.ModelSerializer):
    """Read serializer for categories, including nested children."""

    children = CategoryChildSerializer(many=True, read_only=True)
    image = RelativeImageField(required=False, allow_null=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True, allow_null=True)
    product_count = serializers.SerializerMethodField()
    child_count = serializers.SerializerMethodField()
    full_path = serializers.CharField(read_only=True)

    class Meta:
        model = Category
        fields = (
            "id", "uid", "name", "slug", "parent", "parent_name", "full_path",
            "description", "image", "icon_name", "display_order", "is_featured",
            "is_active", "product_count", "child_count", "children",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "uid", "slug", "children", "created_at", "updated_at")

    def get_product_count(self, obj) -> int:
        return getattr(obj, "products_total", obj.product_count)

    def get_child_count(self, obj) -> int:
        return getattr(obj, "children_total", obj.children.count())


class CategoryWriteSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Category
        fields = (
            "id", "name", "slug", "parent", "description", "image", "icon_name",
            "display_order", "is_featured", "is_active",
        )
        read_only_fields = ("id", "slug")
        # The UniqueTogetherValidator would raise a 400 before validate() runs;
        # we remove it and enforce uniqueness ourselves so duplicates get a
        # meaningful 409 Conflict with an error code.
        validators = []

    def validate_name(self, value):
        value = (value or "").strip()
        if len(value) < 2:
            raise serializers.ValidationError("Category name must be at least 2 characters.")
        return value

    def validate_image(self, value):
        validate_image_file(value)
        return value

    def validate_parent(self, value):
        if value is None:
            return value
        if value.parent_id is not None:
            raise serializers.ValidationError(
                "Categories support a maximum depth of two levels "
                "(a parent cannot itself have a parent)."
            )
        if self.instance and value.pk == self.instance.pk:
            raise serializers.ValidationError("A category cannot be its own parent.")
        return value

    def validate(self, attrs):
        # NOTE: ``parent`` is popped by DRF before validate() runs, so read the
        # raw payload as the source of truth for the uniqueness pre-check.
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if "parent" not in attrs and "parent" in getattr(self, "initial_data", {}):
            parent_id = self.initial_data.get("parent")
            parent = Category.objects.filter(pk=parent_id).first() if parent_id else None
        name = attrs.get("name", getattr(self.instance, "name", None))
        if name:
            queryset = Category.objects.filter(parent=parent, name__iexact=name)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                from common.exceptions import ConflictError

                raise ConflictError(
                    message="A category with this name already exists under the same parent.",
                    code="duplicate_category",
                    details={"name": name, "parent": parent.id if parent else None},
                )
        return attrs


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = (
            "id", "uid", "product", "image", "alt_text", "display_order",
            "is_primary", "created_at", "updated_at",
        )
        read_only_fields = ("id", "uid", "created_at", "updated_at")
        # ``product`` is implied by the nested URL
        # (/products/{id}/images/); the standalone product-images endpoint
        # validates it explicitly in its own view set.
        extra_kwargs = {"product": {"required": False}}

    def validate_image(self, value):
        validate_image_file(value)
        return value


class ProductListSerializer(serializers.ModelSerializer):
    """Compact representation used on listing endpoints."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    parent_category = serializers.CharField(
        source="category.parent.name", read_only=True, allow_null=True
    )
    image_url = serializers.SerializerMethodField()
    unit_label = serializers.CharField(read_only=True)
    discount_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    available_quantity = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id", "uid", "name", "slug", "sku", "brand", "category", "category_name",
            "parent_category", "unit_type", "unit_value", "unit_label", "mrp",
            "selling_price", "discount_percent", "image_url", "primary_image",
            "is_vegetarian", "status", "is_featured", "available_quantity",
            "in_stock", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_image_url(self, obj) -> str | None:
        request = self.context.get("request")
        if not obj.image:
            return None
        try:
            url = obj.image.url
        except ValueError:
            return None
        # Relative, not absolute: the storefront proxies /media to the API, so a
        # path works on any host. build_absolute_uri() baked in the request host
        # (http://127.0.0.1:8000/...), which the browser cannot reach when the
        # page is served from a preview domain - the image then never loads.
        return url

    def get_primary_image(self, obj) -> str | None:
        images = list(obj.images.all())
        primary = next((img for img in images if img.is_primary), images[0] if images else None)
        if primary is None:
            return None
        request = self.context.get("request")
        try:
            url = primary.image.url
        except ValueError:
            return None
        return url


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    category_detail = CategoryChildSerializer(source="category", read_only=True)
    discount_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    max_order_quantity = serializers.IntegerField(read_only=True)
    tax_percent = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + (
            "description", "short_description", "barcode", "tax_percent",
            "max_order_quantity", "discount_amount", "images", "category_detail",
            "display_order",
        )
        read_only_fields = fields


class ProductWriteSerializer(serializers.ModelSerializer):
    """Create / update serializer for products."""

    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    unit_type = serializers.ChoiceField(choices=UnitType.choices, required=False)

    class Meta:
        model = Product
        fields = (
            "id", "name", "slug", "sku", "barcode", "category", "brand",
            "description", "short_description", "unit_type", "unit_value", "mrp",
            "selling_price", "image", "is_vegetarian", "tax_percent",
            "max_order_quantity", "status", "is_featured", "display_order",
        )
        read_only_fields = ("id", "slug")
        extra_kwargs = {
            # Uniqueness is checked in validate() so duplicates return 409.
            "sku": {"required": False, "allow_blank": True, "validators": []},
            "barcode": {"required": False, "allow_blank": True, "validators": []},
        }

    def validate_name(self, value):
        value = (value or "").strip()
        if len(value) < 2:
            raise serializers.ValidationError("Product name must be at least 2 characters.")
        return value

    def validate(self, attrs):
        mrp = attrs.get("mrp", getattr(self.instance, "mrp", None))
        selling_price = attrs.get(
            "selling_price", getattr(self.instance, "selling_price", None)
        )
        if mrp is not None and selling_price is not None and selling_price > mrp:
            raise serializers.ValidationError(
                {"selling_price": "Selling price cannot be greater than MRP."}
            )

        sku = attrs.get("sku")
        if sku:
            queryset = Product.all_objects.filter(sku__iexact=sku)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                from common.exceptions import ConflictError

                raise ConflictError(
                    message="A product with this SKU already exists.",
                    code="duplicate_sku",
                    details={"sku": sku},
                )

        barcode = attrs.get("barcode")
        if barcode:
            queryset = Product.all_objects.filter(barcode=barcode).exclude(
                barcode=""
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                from common.exceptions import ConflictError

                raise ConflictError(
                    message="A product with this barcode already exists.",
                    code="duplicate_barcode",
                    details={"barcode": barcode},
                )
        return attrs

    def validate_image(self, value):
        validate_image_file(value)
        return value


class ProductStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Product.Status.choices)


class CategoryTreeSerializer(serializers.Serializer):
    """Read-only serializer for the category tree endpoint."""

    id = serializers.IntegerField()
    uid = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    icon_name = serializers.CharField()
    image = RelativeImageField(allow_null=True)
    is_featured = serializers.BooleanField()
    display_order = serializers.IntegerField()
    children = serializers.ListField(child=serializers.DictField())
