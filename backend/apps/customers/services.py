"""Business logic for customers. Views must not mutate models directly."""

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.customers.models import Customer, CustomerNote, CustomerStatus
from common.exceptions import BusinessRuleError, ConflictError, ResourceNotFoundError
from common.validators import normalise_mobile

logger = logging.getLogger("apps.customers")


@transaction.atomic
def create_customer(*, full_name, mobile_number, email=None, status=CustomerStatus.ACTIVE,
                    notes="", is_mobile_verified=False) -> Customer:
    """Create a customer, enforcing the unique mobile/email business rules."""
    mobile_number = normalise_mobile(mobile_number)
    email = (email or "").strip().lower() or None

    if Customer.all_objects.filter(mobile_number=mobile_number).exists():
        raise ConflictError(
            message="A customer with this mobile number already exists.",
            code="duplicate_mobile_number",
            details={"mobile_number": mobile_number},
        )
    if email and Customer.all_objects.filter(email=email).exists():
        raise ConflictError(
            message="A customer with this email address already exists.",
            code="duplicate_email",
            details={"email": email},
        )

    try:
        customer = Customer.objects.create(
            full_name=full_name.strip(),
            mobile_number=mobile_number,
            email=email,
            status=status,
            notes=notes or "",
            is_mobile_verified=is_mobile_verified,
        )
    except IntegrityError as exc:  # race between the check and the insert
        raise ConflictError(
            message="A customer with these details already exists.",
            code="duplicate_customer",
        ) from exc

    logger.info("Customer created id=%s mobile=%s", customer.id, customer.mobile_number)
    return customer


@transaction.atomic
def update_customer(customer: Customer, **data) -> Customer:
    """Update the mutable fields of a customer."""
    if "mobile_number" in data and data["mobile_number"]:
        candidate = normalise_mobile(data["mobile_number"])
        clash = (
            Customer.all_objects.filter(mobile_number=candidate)
            .exclude(pk=customer.pk)
            .exists()
        )
        if clash:
            raise ConflictError(
                message="Another customer already uses this mobile number.",
                code="duplicate_mobile_number",
                details={"mobile_number": candidate},
            )
        data["mobile_number"] = candidate

    if "email" in data:
        candidate_email = (data["email"] or "").strip().lower() or None
        if candidate_email:
            clash = (
                Customer.all_objects.filter(email=candidate_email)
                .exclude(pk=customer.pk)
                .exists()
            )
            if clash:
                raise ConflictError(
                    message="Another customer already uses this email address.",
                    code="duplicate_email",
                    details={"email": candidate_email},
                )
        data["email"] = candidate_email

    for field, value in data.items():
        setattr(customer, field, value)
    customer.save()
    logger.info("Customer updated id=%s fields=%s", customer.id, sorted(data))
    return customer


@transaction.atomic
def change_customer_status(customer: Customer, status: str) -> Customer:
    """Activate / deactivate / block a customer."""
    valid = {choice for choice, _ in CustomerStatus.choices}
    if status not in valid:
        raise BusinessRuleError(
            message=f"Invalid status '{status}'.",
            code="invalid_status",
            details={"allowed": sorted(valid)},
        )
    if customer.status == status:
        return customer

    previous = customer.status
    customer.status = status
    customer.save(update_fields=["status", "updated_at"])
    logger.info(
        "Customer status changed id=%s %s -> %s", customer.id, previous, status
    )
    return customer


@transaction.atomic
def delete_customer(customer: Customer) -> None:
    """Delete a customer that has never ordered.

    Customers with order history are blocked from deletion so that financial
    records stay intact; deactivate (status=inactive) instead.
    """
    if customer.orders.exists():
        raise BusinessRuleError(
            message=(
                "This customer has order history and cannot be deleted. "
                "Set the status to 'inactive' or 'blocked' instead."
            ),
            code="customer_has_orders",
            status_code=409,
        )
    customer_id = customer.id
    customer.delete()
    logger.info("Customer deleted id=%s", customer_id)


@transaction.atomic
def record_login(customer: Customer) -> Customer:
    customer.last_login_at = timezone.now()
    customer.save(update_fields=["last_login_at", "updated_at"])
    return customer


@transaction.atomic
def add_customer_note(customer: Customer, *, note: str, author: str = "") -> CustomerNote:
    if not note or not note.strip():
        raise BusinessRuleError(
            message="Note text cannot be empty.", code="empty_note"
        )
    return CustomerNote.objects.create(
        customer=customer, note=note.strip(), author=author or ""
    )


def get_customer_or_404(identifier) -> Customer:
    from apps.customers.selectors import get_customer

    customer = get_customer(identifier)
    if customer is None:
        raise ResourceNotFoundError(
            message=f"Customer '{identifier}' was not found.",
            code="customer_not_found",
        )
    return customer
