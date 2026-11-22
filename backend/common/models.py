"""Abstract models shared by every app.

Keeping these in one place guarantees every table in the system exposes the
same primary key style and the same auditing timestamps.
"""

import uuid

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    """Adds ``created_at`` / ``updated_at`` to a model."""

    created_at = models.DateTimeField(
        default=timezone.now, editable=False, db_index=True
    )
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True
        ordering = ("-created_at",)

    @property
    def age_in_seconds(self) -> float:
        return (timezone.now() - self.created_at).total_seconds()


class UUIDPrimaryKeyModel(models.Model):
    """Integer PK + a public UUID used in URLs so IDs are not enumerable."""

    uid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel, UUIDPrimaryKeyModel):
    """Default base for every concrete domain model."""

    class Meta(TimeStampedModel.Meta):
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that hides soft-deleted rows unless explicitly requested."""

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)

    def delete(self):  # noqa: D102 - soft delete by default
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        """Actually remove the rows (used by tests, smoke cleanup and GDPR)."""
        return super().delete()

    # Convenience alias so callers can write ``.delete(hard=True)``.
    def delete_hard(self):
        return super().delete()


class SoftDeleteManager(models.Manager):
    """Manager returning only non-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Manager that also returns soft-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """Adds soft deletion. Rows remain for order-history integrity."""

    is_deleted = models.BooleanField(default=False, db_index=True, editable=False)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, hard=False):
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        return (1, {self._meta.label: 1})

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])


class PublishableQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        qs = self.filter(is_active=True)
        if any(f.name == "start_date" for f in self.model._meta.get_fields()):
            qs = qs.filter(models.Q(start_date__isnull=True) | models.Q(start_date__lte=now))
        if any(f.name == "end_date" for f in self.model._meta.get_fields()):
            qs = qs.filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=now))
        return qs


class PublishableModel(models.Model):
    """Content that can be switched on/off and scheduled."""

    is_active = models.BooleanField(default=True, db_index=True)

    objects = PublishableQuerySet.as_manager()

    class Meta:
        abstract = True


class SluggedModel(models.Model):
    """Adds a unique slug that is generated from ``name`` when left blank."""

    slug = models.SlugField(max_length=180, unique=True, db_index=True, blank=True)
    slug_source_field = "name"

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._build_unique_slug()
        super().save(*args, **kwargs)

    def _build_unique_slug(self):
        source = getattr(self, self.slug_source_field, "") or ""
        base = slugify(source)[:160] or "item"
        slug = base
        model = type(self)
        counter = 0
        while model._default_manager.filter(slug=slug).exclude(pk=self.pk).exists():
            counter += 1
            slug = f"{base}-{counter}"
        return slug
