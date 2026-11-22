"""Generic selector helpers shared across apps.

A *selector* is a read-only function that returns querysets or aggregates.
Keeping reads here (instead of in views) means the query optimisations
(``select_related`` / ``prefetch_related``) live in one place and are reused by
the API, the admin and the tests.
"""

from django.core.exceptions import ValidationError
from django.db.models import QuerySet


def apply_search(queryset: QuerySet, term: str, fields) -> QuerySet:
    """Apply a case-insensitive OR search across ``fields``."""
    from django.db.models import Q

    if not term:
        return queryset
    query = Q()
    for field in fields:
        query |= Q(**{f"{field}__icontains": term})
    return queryset.filter(query)


def apply_ordering(queryset: QuerySet, ordering: str, allowed) -> QuerySet:
    if not ordering:
        return queryset
    field = ordering.lstrip("-")
    if field not in allowed:
        return queryset
    return queryset.order_by(ordering)


def paginate_queryset(queryset, paginator):
    return paginator.paginate_queryset(queryset, None)


def get_object_or_none(model, **lookups):
    try:
        return model._default_manager.get(**lookups)
    except (model.DoesNotExist, ValidationError, ValueError, TypeError):
        return None


def parse_identifier(identifier):
    """Split an identifier into ``(integer_pk_or_None, uuid_or_None)``.

    Accepts ``12`` (numeric primary key) or a public UUID such as
    ``8f14e45f-ea1f-4c1f-9d1a-0e3a0b6f9c11``. Anything else yields two Nones so
    callers can cleanly return a 404 rather than a database error.
    """
    import uuid as _uuid

    if identifier in (None, ""):
        return None, None

    string_id = str(identifier).strip()
    numeric = int(string_id) if string_id.isdigit() else None
    try:
        public_id = _uuid.UUID(string_id)
    except (ValueError, AttributeError, TypeError):
        public_id = None
    return numeric, public_id


def id_or_uid_q(identifier):
    """Return a Q object matching either the integer pk or the public UUID.

    Returns ``None`` when ``identifier`` is not a valid id of either kind.
    """
    from django.db.models import Q

    numeric, public_id = parse_identifier(identifier)
    if numeric is None and public_id is None:
        return None
    query = Q()
    if numeric is not None:
        query |= Q(pk=numeric)
    if public_id is not None:
        query |= Q(uid=public_id)
    return query
