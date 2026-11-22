"""Put the real pictures of this folder into the UMS Mart database.

After this the same pictures show everywhere: customer store, admin panel
and mobile app. No program code is changed, only the pictures stored for
products, categories and banners.

How to run (Windows PowerShell, PostgreSQL must be running):

    cd C:\\ums_mart\\backend
    C:\\ums_mart\\venv\\Scripts\\python.exe ..\\pictures\\load_pictures.py

What it does:
  * Product   : picture from  products\\<product-name>.jpg
  * Category  : picture from  categories\\<category-name>.jpg
  * Banner    : picture from  banners\\  (fresh, staples or offer)
  * Only the sample colour tiles are replaced. A picture you uploaded in the
    admin panel is kept. Add  --force  to replace those too.
  * The sample "Gallery view" tile of a product is removed.
  * It is safe to run it again.

To add your own picture: name the file like the product, in small letters
with "-" for spaces ("Amul Butter" -> amul-butter.jpg), put it in the
products folder and run the script again with --force.
"""

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"

if not (BACKEND / "manage.py").exists():
    sys.exit(f"Cannot find the backend folder next to this one: {BACKEND}")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import django  # noqa: E402

django.setup()

from django.core.files import File  # noqa: E402
from django.utils.text import slugify  # noqa: E402

from apps.banners.models import Banner  # noqa: E402
from apps.catalog.models import Category, Product, ProductImage  # noqa: E402

FORCE = "--force" in sys.argv

# File names the sample data uses for its colour tiles.
SAMPLE = re.compile(r"^((p|g|c|b)_.*\.png|banner_.*)$")
STAPLES = re.compile(r"staple|rice|atta|dal|grain|flour")


def is_sample(field) -> bool:
    """True when there is no picture, or only the sample colour tile."""
    if not field:
        return True
    return bool(SAMPLE.match(os.path.basename(field.name)))


def find(folder: str, *names: str):
    """First existing picture for one of the names, any allowed type."""
    for name in names:
        if not name:
            continue
        for ending in (".jpg", ".jpeg", ".png", ".webp"):
            path = HERE / folder / f"{name}{ending}"
            if path.exists():
                return path
    return None


def put(obj, field_name: str, path: Path) -> None:
    with path.open("rb") as handle:
        getattr(obj, field_name).save(path.name, File(handle), save=True)


def load_products() -> tuple[int, int, int]:
    done = kept = missing = 0
    for product in Product.objects.all():
        path = find("products", slugify(product.name), product.slug)
        if path is None:
            missing += 1
            print(f"  no picture file for product: {product.name}")
            continue
        if FORCE or is_sample(product.image):
            put(product, "image", path)
            done += 1
        else:
            kept += 1
        # The sample "Gallery view" tile would still be shown first on the
        # product page of the store, so it goes away.
        for extra in ProductImage.objects.filter(product=product):
            if is_sample(extra.image):
                rows = ProductImage.objects.filter(pk=extra.pk)
                getattr(rows, "hard_delete", rows.delete)()
    return done, kept, missing


def load_categories() -> tuple[int, int, int]:
    done = kept = missing = 0
    for category in Category.objects.all():
        path = find("categories", slugify(category.name), category.slug)
        if path is None:
            missing += 1
            print(f"  no picture file for category: {category.name}")
            continue
        if FORCE or is_sample(category.image):
            put(category, "image", path)
            done += 1
        else:
            kept += 1
    return done, kept, missing


def banner_kind(banner) -> str:
    if banner.link_type == "coupon" or banner.linked_coupon_code:
        return "offer"
    text = f"{banner.title} {banner.subtitle}".lower()
    return "staples" if STAPLES.search(text) else "fresh"


def load_banners() -> tuple[int, int, int]:
    done = kept = missing = 0
    for banner in Banner.objects.all():
        kind = banner_kind(banner)
        wide = find("banners", kind)
        small = find("banners/mobile", kind)
        if wide is None:
            missing += 1
            continue
        changed = False
        if FORCE or is_sample(banner.image):
            put(banner, "image", wide)
            changed = True
        if small is not None and (FORCE or is_sample(banner.mobile_image)):
            put(banner, "mobile_image", small)
            changed = True
        if changed:
            done += 1
        else:
            kept += 1
    return done, kept, missing


def main() -> None:
    print("Loading pictures from", HERE)
    for title, work in (
        ("Products", load_products),
        ("Categories", load_categories),
        ("Banners", load_banners),
    ):
        done, kept, missing = work()
        print(f"{title:<11}: {done} updated, {kept} kept as they are, "
              f"{missing} without a picture file")
    print("Done. Reload the store, the admin panel and the mobile app.")


if __name__ == "__main__":
    main()
