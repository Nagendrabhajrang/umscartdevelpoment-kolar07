"""Address business logic."""

import logging

from django.db import transaction

from apps.addresses.models import Address
from common.exceptions import BusinessRuleError, ResourceNotFoundError

logger = logging.getLogger("apps.addresses")

MAX_ADDRESSES_PER_CUSTOMER = 20


@transaction.atomic
def create_address(customer, **data) -> Address:
    customer_id = getattr(customer, "id", customer)
    existing_count = Address.objects.filter(customer_id=customer_id).count()
    if existing_count >= MAX_ADDRESSES_PER_CUSTOMER:
        raise BusinessRuleError(
            message=(
                f"You can save at most {MAX_ADDRESSES_PER_CUSTOMER} addresses. "
                "Delete one to add another."
            ),
            code="address_limit_reached",
            details={"limit": MAX_ADDRESSES_PER_CUSTOMER},
        )

    is_default = data.pop("is_default", False)
    # The very first address is always the default.
    if existing_count == 0:
        is_default = True

    if is_default:
        Address.objects.filter(customer_id=customer_id, is_default=True).update(
            is_default=False
        )

    address = Address(customer_id=customer_id, is_default=is_default, **data)
    address.full_clean(exclude=["uid", "created_at", "updated_at"])
    address.save()
    logger.info("Address created id=%s customer=%s", address.id, customer_id)
    return address


@transaction.atomic
def update_address(address: Address, **data) -> Address:
    make_default = data.pop("is_default", None)
    if make_default:
        Address.objects.filter(
            customer_id=address.customer_id, is_default=True
        ).exclude(pk=address.pk).update(is_default=False)
        address.is_default = True
    elif make_default is False and address.is_default:
        # Refuse to leave the customer without any default address.
        raise BusinessRuleError(
            message=(
                "Set another address as default instead of removing the default "
                "flag from this one."
            ),
            code="default_address_required",
        )

    for field_name, value in data.items():
        setattr(address, field_name, value)
    address.full_clean(exclude=["uid", "created_at", "updated_at"])
    address.save()
    logger.info("Address updated id=%s", address.id)
    return address


@transaction.atomic
def set_default_address(address: Address) -> Address:
    Address.objects.filter(
        customer_id=address.customer_id, is_default=True
    ).exclude(pk=address.pk).update(is_default=False)
    address.is_default = True
    address.save(update_fields=["is_default", "updated_at"])
    logger.info("Default address changed customer=%s address=%s",
                address.customer_id, address.id)
    return address


@transaction.atomic
def delete_address(address: Address) -> None:
    customer_id = address.customer_id
    was_default = address.is_default
    address.delete()
    if was_default:
        replacement = (
            Address.objects.filter(customer_id=customer_id)
            .order_by("-updated_at")
            .first()
        )
        if replacement:
            replacement.is_default = True
            replacement.save(update_fields=["is_default", "updated_at"])
    logger.info("Address deleted id=%s customer=%s", address.id, customer_id)


def get_address_or_404(identifier) -> Address:
    from apps.addresses.selectors import get_address

    address = get_address(identifier)
    if address is None:
        raise ResourceNotFoundError(
            message=f"Address '{identifier}' was not found.", code="address_not_found"
        )
    return address


def get_customer_address_or_404(customer, identifier) -> Address:
    """Fetch an address and assert it belongs to ``customer``."""
    address = get_address_or_404(identifier)
    if address.customer_id != getattr(customer, "id", customer):
        raise ResourceNotFoundError(
            message=f"Address '{identifier}' was not found for this customer.",
            code="address_not_found",
        )
    return address
