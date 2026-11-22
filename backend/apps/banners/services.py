"""Business logic for banners."""

import logging

from django.db import transaction

from apps.banners.models import Banner
from apps.banners.selectors import register_click, register_view
from common.exceptions import BusinessRuleError, ResourceNotFoundError
from common.validators import validate_image_file

logger = logging.getLogger("apps.banners")


@transaction.atomic
def create_banner(**data) -> Banner:
    _validate_link_target(data)
    image = data.get("image")
    if image:
        validate_image_file(image)
    banner = Banner(**data)
    banner.full_clean(exclude=["uid", "created_at", "updated_at"])
    banner.save()
    logger.info("Banner created id=%s placement=%s", banner.id, banner.placement)
    return banner


@transaction.atomic
def update_banner(banner: Banner, **data) -> Banner:
    merged = {
        "link_type": data.get("link_type", banner.link_type),
        "link_url": data.get("link_url", banner.link_url),
        "linked_product": data.get("linked_product", banner.linked_product),
        "linked_category": data.get("linked_category", banner.linked_category),
        "linked_coupon_code": data.get("linked_coupon_code", banner.linked_coupon_code),
    }
    _validate_link_target(merged)
    for field_name, value in data.items():
        setattr(banner, field_name, value)
    banner.full_clean(exclude=["uid", "created_at", "updated_at"])
    banner.save()
    logger.info("Banner updated id=%s", banner.id)
    return banner


@transaction.atomic
def delete_banner(banner: Banner) -> None:
    banner.delete()


@transaction.atomic
def toggle_banner(banner: Banner, is_active: bool) -> Banner:
    banner.is_active = is_active
    banner.save(update_fields=["is_active", "updated_at"])
    return banner


def get_banner_or_404(identifier) -> Banner:
    from apps.banners.selectors import get_banner

    banner = get_banner(identifier)
    if banner is None:
        raise ResourceNotFoundError(
            message=f"Banner '{identifier}' was not found.", code="banner_not_found"
        )
    return banner


def record_view(banner: Banner) -> None:
    register_view(banner)


def record_click(banner: Banner) -> str:
    """Count a click and return the destination URL."""
    register_click(banner)
    return banner.resolved_link


def _validate_link_target(data: dict) -> None:
    link_type = data.get("link_type") or "none"
    if link_type == "url" and not data.get("link_url"):
        raise BusinessRuleError(
            message="A link URL is required when link_type is 'url'.",
            code="invalid_banner_link",
        )
    if link_type == "product" and not data.get("linked_product"):
        raise BusinessRuleError(
            message="A product must be selected when link_type is 'product'.",
            code="invalid_banner_link",
        )
    if link_type == "category" and not data.get("linked_category"):
        raise BusinessRuleError(
            message="A category must be selected when link_type is 'category'.",
            code="invalid_banner_link",
        )
    if link_type == "coupon" and not data.get("linked_coupon_code"):
        raise BusinessRuleError(
            message="A coupon code is required when link_type is 'coupon'.",
            code="invalid_banner_link",
        )
