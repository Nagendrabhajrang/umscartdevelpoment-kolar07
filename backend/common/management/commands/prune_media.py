"""Delete media files nothing points at any more.

Re-running ``seed_data`` regenerates images with fresh file names, so the old
PNGs stay on disk as unreferenced orphans. Over a handful of seeds that quietly
doubles the size of ``backend/media``. This command walks MEDIA_ROOT and deletes
every file that is not referenced by a model field.

    python manage.py prune_media --dry-run     # list what would go
    python manage.py prune_media               # delete it
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand


def referenced_media_names() -> set[str]:
    """Every file name pointed at by any FileField/ImageField in the project.

    Introspected rather than hand-listed: the first version of this command
    named the fields it knew about and missed ``Product.image`` and
    ``OrderItem.product_image``, which deleted thumbnails that were still in use.
    """
    from django.apps import apps

    used: set[str] = set()
    for model in apps.get_models():
        file_fields = [
            field for field in model._meta.get_fields()
            if field.__class__.__name__ in {"FileField", "ImageField"}
        ]
        if not file_fields:
            continue
        names = [field.name for field in file_fields]
        for row in model._default_manager.values_list(*names).iterator():
            for value in row:
                if value:
                    used.add(str(value).replace("\\", "/"))
    return used


class Command(BaseCommand):
    help = "Delete media files that no model row references."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report.")

    def handle(self, *args, **options):
        media_root = str(settings.MEDIA_ROOT)
        if not os.path.isdir(media_root):
            self.stdout.write("No media directory; nothing to prune.")
            return

        used = referenced_media_names()
        orphans: list[tuple[str, int]] = []
        for root, _dirs, files in os.walk(media_root):
            for name in files:
                absolute = os.path.join(root, name)
                relative = os.path.relpath(absolute, media_root).replace("\\", "/")
                if relative not in used:
                    orphans.append((relative, os.path.getsize(absolute)))

        freed = sum(size for _rel, size in orphans)
        if not orphans:
            self.stdout.write(self.style.SUCCESS("Nothing to prune - every file is referenced."))
            return

        for relative, size in sorted(orphans):
            if not options["dry_run"]:
                os.remove(os.path.join(media_root, relative))
            self.stdout.write(f"  {'would delete' if options['dry_run'] else 'deleted'} {relative} ({size // 1024} KB)")

        verb = "Would free" if options["dry_run"] else "Freed"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {freed / 1_048_576:.2f} MB across {len(orphans)} orphan file(s)."
            )
        )
