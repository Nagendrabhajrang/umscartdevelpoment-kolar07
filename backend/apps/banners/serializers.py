"""Serializers for banners."""

from rest_framework import serializers

from apps.banners.models import Banner, BannerPlacement
from common.validators import validate_image_file


class BannerSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    mobile_image_url = serializers.SerializerMethodField()
    placement_display = serializers.CharField(source="get_placement_display", read_only=True)
    resolved_link = serializers.CharField(read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = Banner
        fields = (
            "id", "uid", "title", "subtitle", "image", "image_url", "mobile_image",
            "mobile_image_url", "alt_text", "placement", "placement_display",
            "link_type", "link_url", "linked_product", "linked_category",
            "linked_coupon_code", "resolved_link", "display_order", "is_active",
            "is_live", "start_date", "end_date", "click_count", "view_count",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "uid", "click_count", "view_count", "created_at", "updated_at",
        )

    def _absolute(self, field):
        if not field:
            return None
        request = self.context.get("request")
        try:
            url = field.url
        except ValueError:
            return None
        return url  # relative: /media is proxied by the frontend

    def get_image_url(self, obj) -> str | None:
        return self._absolute(obj.image)

    def get_mobile_image_url(self, obj) -> str | None:
        return self._absolute(obj.mobile_image)


class BannerWriteSerializer(serializers.ModelSerializer):
    placement = serializers.ChoiceField(choices=BannerPlacement.choices, required=False)

    class Meta:
        model = Banner
        fields = (
            "title", "subtitle", "image", "mobile_image", "alt_text", "placement",
            "link_type", "link_url", "linked_product", "linked_category",
            "linked_coupon_code", "display_order", "is_active", "start_date", "end_date",
        )

    def validate_image(self, value):
        validate_image_file(value)
        return value

    def validate_mobile_image(self, value):
        validate_image_file(value)
        return value

    def validate(self, attrs):
        link_type = attrs.get("link_type", getattr(self.instance, "link_type", "none"))
        link_url = attrs.get("link_url", getattr(self.instance, "link_url", ""))

        if link_type == "url" and not link_url:
            raise serializers.ValidationError(
                {"link_url": "A link URL is required when link_type is 'url'."}
            )
        if link_type == "product" and not attrs.get(
            "linked_product", getattr(self.instance, "linked_product", None)
        ):
            raise serializers.ValidationError(
                {"linked_product": "Select a product when link_type is 'product'."}
            )
        if link_type == "category" and not attrs.get(
            "linked_category", getattr(self.instance, "linked_category", None)
        ):
            raise serializers.ValidationError(
                {"linked_category": "Select a category when link_type is 'category'."}
            )
        if link_type == "coupon" and not attrs.get(
            "linked_coupon_code", getattr(self.instance, "linked_coupon_code", "")
        ):
            raise serializers.ValidationError(
                {"linked_coupon_code": "Enter a coupon code when link_type is 'coupon'."}
            )

        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": "End date must be after the start date."}
            )
        return attrs


class BannerToggleSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class BannerTrackSerializer(serializers.Serializer):
    event = serializers.ChoiceField(choices=[("view", "View"), ("click", "Click")])

    class Meta:
        ref_name = "BannerTrack"
