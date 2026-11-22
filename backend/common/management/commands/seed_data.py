"""Seed UMS Mart with realistic demo data.

Usage:
    python manage.py seed_data              # idempotent, safe to re-run
    python manage.py seed_data --flush      # wipe demo data first

The command is intentionally deterministic: SKUs, slugs and store settings are
stable so repeated runs do not create duplicates.
"""

import hashlib
import io
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.addresses.models import Address, AddressLabel
from apps.banners.models import Banner, BannerPlacement
from apps.catalog.models import Category, Product, ProductImage, UnitType
from apps.customers.models import Customer
from apps.inventory.services import add_stock, set_initial_stock
from apps.orders.models import Order
from apps.payments.models import Payment, Refund
from apps.promotions.models import AppliesTo, DiscountType, Promotion
from apps.store_settings.models import DeliverySlab, StoreSettings


class Command(BaseCommand):
    help = "Populate the database with UMS Mart demonstration data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing demo rows before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing demo data...")
            # Activity first: orders hold FKs to products/customers, so they
            # must go before the catalogue or the delete would cascade oddly.
            # Payments protect their order (financial records), so refunds and
            # payments are removed explicitly before the orders themselves.
            Refund.objects.all().delete()
            Payment.objects.all().delete()
            Order.objects.all().delete()
            Promotion.objects.all().delete()
            Banner.objects.all().delete()
            DeliverySlab.objects.all().delete()
            # Products are soft-deleted on purpose (order history keeps the FK),
            # but a demo reset wants the rows gone, so hard-delete explicitly.
            for product in Product.all_objects.all():
                product.delete(hard=True)
            # Children must go before their parent, or PROTECT on
            # Category.parent blocks the delete. Two passes = two levels.
            Category.objects.exclude(parent=None).delete()
            Category.objects.filter(parent=None).delete()

        settings_obj = self._seed_store_settings()
        categories = self._seed_categories()
        products = self._seed_products(categories)
        self._seed_initial_stock(products)
        customers = self._seed_customers()
        self._seed_addresses(customers)
        self._seed_promotions(categories, products)
        self._seed_banners(categories)
        self._seed_images(products)
        self._seed_orders(customers, products)

        self.stdout.write(self.style.SUCCESS("\nDemo data ready."))
        self.stdout.write(f"  Store settings : {settings_obj.store_name}")
        self.stdout.write(f"  Categories     : {Category.objects.count()}")
        self.stdout.write(f"  Products       : {Product.objects.count()}")
        self.stdout.write(f"  Customers      : {Customer.objects.count()}")
        self.stdout.write(f"  Promotions     : {Promotion.objects.count()}")
        self.stdout.write(f"  Banners        : {Banner.objects.count()}")
        self.stdout.write(f"  Orders         : {Order.objects.count()}")
        self.stdout.write(f"  Payments       : {Payment.objects.count()}")
        banner_images = Banner.objects.exclude(image="").count()
        self.stdout.write(
            f"  Images         : {ProductImage.objects.count()} product, {banner_images} banner"
        )
        self.stdout.write(
            "\nTry it:\n"
            "  curl -H 'X-Customer-Id: 1' http://127.0.0.1:8000/api/v1/cart/\n"
            "  Swagger docs: http://127.0.0.1:8000/api/docs/\n"
        )

    # ------------------------------------------------------------------
    def _seed_orders(self, customers, products):
        """Replay a few months of shopper activity through the real services.

        Orders are created by :func:`apps.orders.services.checkout`, so stock
        movements, payment rows and status history stay exactly as the API
        would leave them. Nothing is written by hand. Idempotent: a customer
        that already has orders is skipped, so re-running never duplicates.
        """
        import random

        from apps.orders.models import Order, OrderStatus
        from apps.orders.services import checkout, update_order_status
        from apps.payments.models import Payment, PaymentMethod
        from apps.payments.services import mark_cod_collected

        from apps.cart.services import add_to_cart, get_or_create_active_cart

        rng = random.Random(20261109)  # fixed seed -> same demo data every run
        basket_pool = [
            name for name in products
            if name in {
                "Banana Robusta", "Shimla Apple", "Tomato Local", "Amul Taaza Toned Milk",
                "Britannia Brown Bread", "Amul Butter", "Parle-G Biscuits",
                "Lay's Classic Salted", "Toor Dal", "India Gate Basmati Rice",
                "Aashirvaad Shudh Chakki Atta", "Amul Masti Dahi",
                "Tata Tea Premium", "Surf Excel Easy Wash", "Vim Dishwash Gel",
                "Green Capsicum", "Baby Spinach", "Good Day Cashew Cookies",
            }
        ]
        # name -> how many past orders to replay, and the lifecycle to walk
        plan = {
            customers[0]: [("delivered", 6), ("out_for_delivery", 1)],
            customers[1]: [("delivered", 3), ("cancelled", 1)],
            customers[2]: [("delivered", 2), ("processing", 1)],
            customers[3]: [("delivered", 1), ("pending", 1)],
        }
        walk = [
            OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.PACKED,
            OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED,
        ]
        created = 0
        for customer, stages in plan.items():
            if Order.objects.filter(customer=customer).exists():
                continue
            address = customer.addresses.filter(is_default=True).first() \
                or customer.addresses.first()
            if address is None:
                continue
            for final_status, count in stages:
                for _ in range(count):
                    for name in rng.sample(sorted(basket_pool), rng.randint(2, 4)):
                        add_to_cart(customer, products[name][0], rng.randint(1, 2))
                    order = checkout(
                        customer=customer,
                        address=address,
                        payment_method=PaymentMethod.COD,
                    )
                    created += 1

                    payment = order.payments.first()
                    if final_status == "cancelled":
                        continue

                    steps = walk[:walk.index(final_status) + 1] if final_status in walk else []

                    steps = walk[:walk.index(final_status) + 1] if final_status in walk else []
                    for status in steps:
                        # Cash-first: update_order_status() refuses to deliver an order
                        # whose cash is not recorded (payment_required_before_delivery),
                        # so collect before the DELIVERED transition, not after it.
                        if (
                            status == OrderStatus.DELIVERED
                            and payment is not None
                            and final_status == "delivered"
                        ):
                            mark_cod_collected(payment, collected_by="seed_data")
                        update_order_status(order, status, changed_by="seed_data")


        self.stdout.write(f"  orders replayed: {created}")

    @staticmethod
    def _hsl(hue, saturation, lightness):
        """Minimal HSL -> RGB, used for the placeholder palette."""
        import colorsys
        r, g, b = colorsys.hls_to_rgb(hue / 360.0, lightness, saturation)
        return (int(r * 255), int(g * 255), int(b * 255))

    # ------------------------------------------------------------------
    def _seed_images(self, products):
        """Give every product and banner a real image file.

        Generated with Pillow instead of downloaded so the command works
        offline, and deterministic (the colour derives from the name) so
        re-running produces identical files. Only fills empty image fields, so
        an admin's uploaded photo is never overwritten.
        """
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.stdout.write(self.style.WARNING(
                "  images skipped: Pillow is not installed"))
            return

        def plate(title, subtitle, size, hue_seed, variant=0, inner_name="seed.png"):
            """A soft gradient tile with the product initials.

            Generated locally (no network) and deterministic, so repeated runs
            overwrite with byte-identical files. A banner gets a wide canvas and
            no rounded corners; a product tile is square.
            """
            digest = hashlib.sha256(f"{hue_seed}-{variant}".encode()).digest()
            w, h = size
            # Pick a pastel pair instead of one flat colour.
            hue = (digest[0] * 360) / 256.0
            def shade(light):
                return Image.new("RGB", (1, 1), self._hsl(hue, 0.45, light)).getpixel((0, 0))
            top, bottom = shade(0.72), shade(0.52)

            # Vertical gradient, computed one row at a time and stretched.
            gradient = Image.new("RGB", (1, h))
            for y in range(h):
                t = y / max(h - 1, 1)
                gradient.putpixel((0, y), tuple(
                    round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
            img = gradient.resize((w, h))

            draw = ImageDraw.Draw(img, "RGBA")
            initials = "".join(part[0] for part in title.split()[:2]).upper() or "UM"
            box = max(w // 5, 48)
            unit = w / 600.0
            draw.rounded_rectangle(
                [(w - box) / 2, (h - box) / 2 - 30 * unit, (w + box) / 2, (h + box) / 2 - 30 * unit],
                radius=int(box * 0.28), fill=(255, 255, 255, 46),
            )
            draw.text(((w - draw.textlength(initials, font_size=int(box * 0.52))) / 2,
                       (h - box) / 2 - 30 * unit + box * 0.24),
                      initials, fill=(255, 255, 255, 235), font_size=int(box * 0.52))
            if subtitle:
                font_size = int(24 * unit) or 12
                draw.text(((w - draw.textlength(subtitle, font_size=font_size)) / 2,
                           h * 0.82), subtitle,
                          fill=(255, 255, 255, 215), font_size=font_size)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            return ContentFile(buffer.getvalue(), name=inner_name)

        made = 0
        for name, (product, _qty) in products.items():
            if product.image:
                continue
            slug = name.lower().replace(" ", "-").replace("'", "")[:40]
            product.image.save(
                f"p_{slug}.png",
                plate(name, product.unit_label, (600, 600), name, inner_name=f"p_{slug}.png"),
                save=True,
            )
            made += 1

            # A second gallery image for the detail page.
            if not product.images.exists():
                ProductImage.objects.create(
                    product=product,
                    image=plate(
                        name, "Gallery view", (600, 600), name, variant=1,
                        inner_name=f"g_{slug}.png",
                    ),
                    alt_text=f"{name} - alternate view",
                    display_order=1,
                )

        # Category tiles: the home page renders circles from these.
        for category in Category.objects.order_by("id"):
            if category.image:
                continue
            # Full name so "Biscuits & Cookies" reads as BC, not B.
            category.image.save(
                f"c_{category.slug}.png",
                plate(category.name.replace("&", " "), "", (400, 400), f"cat{category.id}",
                      inner_name=f"c_{category.slug}.png"),
                save=True,
            )
            made += 1

        for index, banner in enumerate(Banner.objects.filter(image="")):
            banner.image.save(
                f"b_{banner.id}.png",
                plate(banner.title, banner.subtitle or "", (1200, 500), f"banner{banner.id}",
                      inner_name=f"b_{banner.id}.png"),
                save=True,
            )
            made += 1

        self.stdout.write(f"  images generated: {made}")

    # ------------------------------------------------------------------
    def _seed_store_settings(self):
        settings_obj = StoreSettings.load()
        settings_obj.store_name = "UMS Mart"
        settings_obj.tagline = "Fresh groceries, delivered in 45 minutes"
        settings_obj.contact_phone = "+919876543210"
        settings_obj.contact_email = "support@umsmart.local"
        settings_obj.address = "12 MG Road, Bengaluru, Karnataka 560001, India"
        settings_obj.delivery_charge = Decimal("40.00")
        settings_obj.free_delivery_threshold = Decimal("499.00")
        settings_obj.minimum_order_value = Decimal("99.00")
        settings_obj.delivery_eta_minutes = 45
        settings_obj.default_tax_percent = Decimal("5.00")
        settings_obj.packaging_charge = Decimal("5.00")
        settings_obj.upi_id = "umsmart@okhdfcbank"
        settings_obj.upi_payee_name = "UMS Mart"
        settings_obj.cod_instructions = (
            "Please keep exact change ready. Our delivery partner cannot "
            "provide change above ₹100."
        )
        settings_obj.is_store_open = True
        settings_obj.save()

        slabs = [
            ("Below ₹199", 0, 198.99, 40),
            ("₹199 - ₹398", 199, 398.99, 30),
            ("₹399 - ₹498", 399, 498.99, 20),
            ("₹499 and above", 499, None, 0),
        ]
        for name, low, high, charge in slabs:
            DeliverySlab.objects.get_or_create(
                name=name,
                defaults={
                    "min_order_value": Decimal(str(low)),
                    "max_order_value": Decimal(str(high)) if high is not None else None,
                    "delivery_charge": Decimal(str(charge)),
                },
            )
        return settings_obj

    # ------------------------------------------------------------------
    def _seed_categories(self):
        tree = {
            "Fruits & Vegetables": ["Fresh Fruits", "Fresh Vegetables", "Herbs & Seasonings"],
            "Dairy & Breakfast": [
                "Milk & Curd", "Bread & Eggs", "Butter & Cheese", "Breakfast Cereals",
            ],
            "Staples & Grains": [
                "Rice & Rice Products", "Atta & Flours", "Dal & Pulses",
                "Oils & Ghee", "Masalas & Spices",
            ],
            "Snacks & Beverages": [
                "Biscuits & Cookies", "Chips & Namkeen", "Tea & Coffee",
                "Cold Drinks & Juices", "Noodles & Sauces", "Chocolates & Sweets",
            ],
            "Home & Personal Care": ["Detergents", "Soaps & Shampoos", "Cleaning Supplies"],
        }
        icons = {
            "Fruits & Vegetables": "carrot",
            "Dairy & Breakfast": "milk",
            "Staples & Grains": "rice",
            "Snacks & Beverages": "cookie",
            "Home & Personal Care": "sparkles",
        }
        result = {}
        for order, (parent_name, children) in enumerate(tree.items()):
            parent, _ = Category.objects.get_or_create(
                name=parent_name,
                parent=None,
                defaults={
                    "description": f"All {parent_name.lower()} products.",
                    "icon_name": icons.get(parent_name, ""),
                    "display_order": order,
                    "is_featured": order < 3,
                },
            )
            result[parent_name] = parent
            for child_order, child_name in enumerate(children):
                child, _ = Category.objects.get_or_create(
                    name=child_name,
                    parent=parent,
                    defaults={"display_order": child_order},
                )
                result[child_name] = child
        self.stdout.write(f"  categories: {Category.objects.count()}")
        return result

    # ------------------------------------------------------------------
    def _seed_products(self, categories):
        catalogue = [
            # name, category, brand, unit_type, unit_value, mrp, price, initial qty
            ("Banana Robusta", "Fresh Fruits", "Farm Fresh", UnitType.DOZEN, 1, 60, 48, 120),
            ("Shimla Apple", "Fresh Fruits", "Farm Fresh", UnitType.KILOGRAM, 1, 210, 179, 80),
            ("Nagpur Orange", "Fresh Fruits", "Farm Fresh", UnitType.KILOGRAM, 1, 120, 99, 60),
            ("Tomato Local", "Fresh Vegetables", "Farm Fresh", UnitType.KILOGRAM, 1, 45, 32, 150),
            ("Baby Spinach", "Fresh Vegetables", "Farm Fresh", UnitType.BUNCH, 1, 30, 24, 90),
            ("Green Capsicum", "Fresh Vegetables", "Farm Fresh", UnitType.GRAM, 500, 55, 42, 70),
            ("Coriander Leaves", "Herbs & Seasonings", "Farm Fresh", UnitType.BUNCH, 1, 20, 15, 100),
            ("Mint Leaves", "Herbs & Seasonings", "Farm Fresh", UnitType.BUNCH, 1, 18, 12, 85),
            ("Amul Taaza Toned Milk", "Milk & Curd", "Amul", UnitType.LITRE, 1, 68, 66, 200),
            ("Amul Masti Dahi", "Milk & Curd", "Amul", UnitType.GRAM, 400, 55, 50, 120),
            ("Britannia Brown Bread", "Bread & Eggs", "Britannia", UnitType.PACK, 1, 55, 50, 90),
            ("Farm Eggs (6 pcs)", "Bread & Eggs", "Eggoz", UnitType.PACK, 6, 75, 68, 70),
            ("Amul Butter", "Butter & Cheese", "Amul", UnitType.GRAM, 500, 285, 265, 60),
            ("Amul Cheese Slices", "Butter & Cheese", "Amul", UnitType.PACK, 200, 145, 132, 45),
            ("India Gate Basmati Rice", "Rice & Rice Products", "India Gate", UnitType.KILOGRAM, 5, 720, 649, 55),
            ("Sona Masoori Rice", "Rice & Rice Products", "Daawat", UnitType.KILOGRAM, 5, 480, 429, 65),
            ("Aashirvaad Shudh Chakki Atta", "Atta & Flours", "Aashirvaad", UnitType.KILOGRAM, 5, 320, 289, 110),
            ("Bansi Rava", "Atta & Flours", "MTR", UnitType.GRAM, 500, 65, 58, 40),
            ("Toor Dal", "Dal & Pulses", "Tata Sampann", UnitType.KILOGRAM, 1, 190, 172, 100),
            ("Moong Dal Yellow", "Dal & Pulses", "Tata Sampann", UnitType.KILOGRAM, 1, 165, 149, 95),
            ("Parle-G Biscuits", "Biscuits & Cookies", "Parle", UnitType.PACK, 800, 90, 82, 200),
            ("Good Day Cashew Cookies", "Biscuits & Cookies", "Britannia", UnitType.PACK, 200, 45, 40, 180),
            ("Lay's Classic Salted", "Chips & Namkeen", "Lay's", UnitType.PACK, 52, 20, 18, 250),
            ("Haldiram's Aloo Bhujia", "Chips & Namkeen", "Haldiram's", UnitType.PACK, 200, 60, 54, 130),
            ("Tata Tea Premium", "Tea & Coffee", "Tata Tea", UnitType.GRAM, 500, 275, 249, 75),
            ("Nescafe Classic", "Tea & Coffee", "Nescafe", UnitType.GRAM, 100, 320, 289, 50),
            ("Surf Excel Easy Wash", "Detergents", "Surf Excel", UnitType.KILOGRAM, 1, 125, 112, 90),
            ("Ariel Matic Liquid", "Detergents", "Ariel", UnitType.LITRE, 1, 380, 345, 40),
            ("Dove Cream Beauty Bar", "Soaps & Shampoos", "Dove", UnitType.PACK, 3, 210, 189, 65),
            ("Colgate Strong Teeth", "Soaps & Shampoos", "Colgate", UnitType.GRAM, 200, 110, 99, 85),
            ("Harpic Toilet Cleaner", "Cleaning Supplies", "Harpic", UnitType.LITRE, 1, 210, 189, 55),
            ("Vim Dishwash Gel", "Cleaning Supplies", "Vim", UnitType.MILLILITRE, 750, 215, 195, 60),
            # ---- second batch: more items in every aisle ----
            ("Pomegranate", "Fresh Fruits", "Farm Fresh", UnitType.KILOGRAM, 1, 220, 189, 70),
            ("Green Grapes", "Fresh Fruits", "Farm Fresh", UnitType.GRAM, 500, 90, 75, 60),
            ("Onion", "Fresh Vegetables", "Farm Fresh", UnitType.KILOGRAM, 1, 45, 36, 200),
            ("Potato", "Fresh Vegetables", "Farm Fresh", UnitType.KILOGRAM, 1, 40, 30, 220),
            ("Carrot", "Fresh Vegetables", "Farm Fresh", UnitType.GRAM, 500, 45, 38, 90),
            ("Ginger", "Herbs & Seasonings", "Farm Fresh", UnitType.GRAM, 250, 40, 32, 80),
            ("Lemon", "Herbs & Seasonings", "Farm Fresh", UnitType.PIECE, 4, 30, 24, 120),
            ("Green Chilli", "Herbs & Seasonings", "Farm Fresh", UnitType.GRAM, 100, 15, 12, 100),
            ("Amul Fresh Paneer", "Butter & Cheese", "Amul", UnitType.GRAM, 200, 95, 88, 50),
            ("Kellogg's Corn Flakes", "Breakfast Cereals", "Kellogg's", UnitType.GRAM, 475, 210, 189, 60),
            ("Quaker Oats", "Breakfast Cereals", "Quaker", UnitType.KILOGRAM, 1, 215, 195, 55),
            ("Fortune Sunlite Sunflower Oil", "Oils & Ghee", "Fortune", UnitType.LITRE, 1, 165, 149, 90),
            ("Amul Pure Ghee", "Oils & Ghee", "Amul", UnitType.LITRE, 1, 680, 645, 40),
            ("Saffola Gold Oil", "Oils & Ghee", "Saffola", UnitType.LITRE, 1, 199, 185, 60),
            ("Everest Garam Masala", "Masalas & Spices", "Everest", UnitType.GRAM, 100, 92, 85, 80),
            ("Everest Turmeric Powder", "Masalas & Spices", "Everest", UnitType.GRAM, 200, 78, 70, 90),
            ("Tata Salt", "Masalas & Spices", "Tata", UnitType.KILOGRAM, 1, 28, 26, 250),
            ("Kabuli Chana", "Dal & Pulses", "Tata Sampann", UnitType.KILOGRAM, 1, 180, 159, 70),
            ("Coca-Cola", "Cold Drinks & Juices", "Coca-Cola", UnitType.MILLILITRE, 750, 45, 40, 150),
            ("Real Mixed Fruit Juice", "Cold Drinks & Juices", "Real", UnitType.LITRE, 1, 130, 115, 70),
            ("Bisleri Mineral Water", "Cold Drinks & Juices", "Bisleri", UnitType.LITRE, 1, 20, 18, 300),
            ("Mango Frooti", "Cold Drinks & Juices", "Frooti", UnitType.MILLILITRE, 600, 40, 36, 110),
            ("Maggi 2-Minute Noodles", "Noodles & Sauces", "Maggi", UnitType.PACK, 4, 60, 56, 220),
            ("Kissan Fresh Tomato Ketchup", "Noodles & Sauces", "Kissan", UnitType.GRAM, 950, 150, 135, 65),
            ("Cadbury Dairy Milk Silk", "Chocolates & Sweets", "Cadbury", UnitType.GRAM, 150, 185, 170, 90),
            ("Nestle KitKat", "Chocolates & Sweets", "Nestle", UnitType.GRAM, 37, 30, 28, 160),
            ("Oreo Vanilla Creme Biscuits", "Biscuits & Cookies", "Oreo", UnitType.GRAM, 120, 40, 35, 140),
            ("Kurkure Masala Munch", "Chips & Namkeen", "Kurkure", UnitType.GRAM, 90, 20, 18, 200),
            ("Bru Instant Coffee", "Tea & Coffee", "Bru", UnitType.GRAM, 100, 250, 229, 60),
            ("Tide Plus Detergent Powder", "Detergents", "Tide", UnitType.KILOGRAM, 1, 130, 118, 80),
            ("Head & Shoulders Shampoo", "Soaps & Shampoos", "Head & Shoulders", UnitType.MILLILITRE, 340, 399, 359, 45),
            ("Dettol Liquid Handwash", "Soaps & Shampoos", "Dettol", UnitType.MILLILITRE, 200, 109, 99, 75),
            ("Lizol Floor Cleaner", "Cleaning Supplies", "Lizol", UnitType.MILLILITRE, 975, 245, 219, 60),
            ("Colin Glass Cleaner", "Cleaning Supplies", "Colin", UnitType.MILLILITRE, 500, 120, 108, 50),
        ]

        created = {}
        for name, category_name, brand, unit_type, unit_value, mrp, price, qty in catalogue:
            category = categories[category_name]
            product, _ = Product.all_objects.get_or_create(
                name=name,
                defaults={
                    "category": category,
                    "brand": brand,
                    "unit_type": unit_type,
                    "unit_value": Decimal(str(unit_value)),
                    "mrp": Decimal(str(mrp)),
                    "selling_price": Decimal(str(price)),
                    "short_description": f"{name} - quality checked and delivered fresh.",
                    "description": (
                        f"Buy {name} online at UMS Mart. Sourced from trusted "
                        "suppliers, quality checked before dispatch, and delivered "
                        "to your doorstep."
                    ),
                    "tax_percent": Decimal("5.00") if category.parent.name in {
                        "Staples & Grains", "Snacks & Beverages"
                    } else Decimal("0.00"),
                    "is_featured": name in {
                        "Amul Taaza Toned Milk", "Banana Robusta",
                        "Aashirvaad Shudh Chakki Atta", "India Gate Basmati Rice",
                    },
                },
            )
            created[name] = (product, qty)
        self.stdout.write(f"  products: {Product.objects.count()}")
        return created

    # ------------------------------------------------------------------
    def _seed_initial_stock(self, products):
        for product, qty in products.values():
            set_initial_stock(product, quantity=0)
            stock = product.stock
            if stock.quantity == 0:
                add_stock(
                    product,
                    qty,
                    reference="SEED",
                    reason="Demo initial stock",
                    performed_by="seed_data",
                )

    # ------------------------------------------------------------------
    def _seed_customers(self):
        customers = [
            ("Aarav Sharma", "+919876500001", "aarav.sharma@example.com"),
            ("Diya Patel", "+919876500002", "diya.patel@example.com"),
            ("Kabir Nair", "+919876500003", "kabir.nair@example.com"),
            ("Meera Iyer", "+919876500004", "meera.iyer@example.com"),
        ]
        created = []
        for name, mobile, email in customers:
            customer, _ = Customer.objects.get_or_create(
                mobile_number=mobile,
                defaults={"full_name": name, "email": email},
            )
            created.append(customer)
        self.stdout.write(f"  customers: {Customer.objects.count()}")
        return created

    # ------------------------------------------------------------------
    def _seed_addresses(self, customers):
        addresses = [
            ("12, Sunrise Apartments", "4th Cross, Indiranagar", "Near Metro Station",
             "Bengaluru", "Karnataka", "560038"),
            ("45, Lake View Residency", "Sarjapur Road", "Opposite Wipro Gate",
             "Bengaluru", "Karnataka", "560035"),
        ]
        for customer in customers:
            for index, (line1, line2, landmark, city, state, pincode) in enumerate(addresses):
                Address.objects.get_or_create(
                    customer=customer,
                    line1=line1,
                    defaults={
                        "label": AddressLabel.HOME if index == 0 else AddressLabel.WORK,
                        "recipient_name": customer.full_name,
                        "recipient_mobile": customer.mobile_number,
                        "line2": line2,
                        "landmark": landmark,
                        "city": city,
                        "state": state,
                        "pincode": pincode,
                        "is_default": index == 0,
                        "delivery_instructions": "Ring the bell twice." if index == 0 else "",
                    },
                )
        self.stdout.write(f"  addresses: {Address.objects.count()}")

    # ------------------------------------------------------------------
    def _seed_promotions(self, categories, products):
        from datetime import timedelta

        from django.utils import timezone

        now = timezone.now()

        Promotion.objects.get_or_create(
            code="WELCOME100",
            defaults={
                "name": "Welcome offer - ₹100 off",
                "description": "Flat ₹100 off on orders above ₹499.",
                "discount_type": DiscountType.FIXED,
                "discount_value": Decimal("100.00"),
                "min_order_value": Decimal("499.00"),
                "applies_to": AppliesTo.ALL,
                "start_date": now - timedelta(days=1),
                "end_date": now + timedelta(days=90),
                "usage_limit_total": 500,
                "usage_limit_per_customer": 1,
                "first_order_only": True,
                "is_visible": True,
                "priority": 10,
            },
        )
        Promotion.objects.get_or_create(
            code="FRESH10",
            defaults={
                "name": "10% off on fruits & vegetables",
                "description": "Save 10% on the fruits and vegetables category, up to ₹75.",
                "discount_type": DiscountType.PERCENTAGE,
                "discount_value": Decimal("10.00"),
                "max_discount_amount": Decimal("75.00"),
                "min_order_value": Decimal("199.00"),
                "applies_to": AppliesTo.CATEGORY,
                "category": categories["Fruits & Vegetables"],
                "start_date": now - timedelta(days=1),
                "end_date": now + timedelta(days=30),
                "usage_limit_total": None,
                "usage_limit_per_customer": 5,
                "is_visible": True,
                "priority": 5,
            },
        )
        Promotion.objects.get_or_create(
            code="FREESHIP",
            defaults={
                "name": "Free delivery",
                "description": "No delivery charge on any order.",
                "discount_type": DiscountType.FREE_DELIVERY,
                "discount_value": Decimal("0.00"),
                "min_order_value": Decimal("0.00"),
                "applies_to": AppliesTo.ALL,
                "start_date": now - timedelta(days=1),
                "end_date": now + timedelta(days=60),
                "usage_limit_per_customer": 3,
                "is_visible": True,
                "priority": 1,
            },
        )
        # Automatic (code-less) offer: 5% off staples.
        auto, _ = Promotion.objects.get_or_create(
            name="Staples 5% off (automatic)",
            code=None,
            defaults={
                "description": "Automatic 5% discount on the staples category.",
                "discount_type": DiscountType.PERCENTAGE,
                "discount_value": Decimal("5.00"),
                "max_discount_amount": Decimal("50.00"),
                "applies_to": AppliesTo.CATEGORY,
                "category": categories["Staples & Grains"],
                "start_date": now - timedelta(days=1),
                "end_date": now + timedelta(days=45),
                "is_visible": False,
                "priority": 2,
            },
        )
        self.stdout.write(f"  promotions: {Promotion.objects.count()}")

    # ------------------------------------------------------------------
    def _seed_banners(self, categories):
        banners = [
            ("Fresh groceries in 45 minutes", "Free delivery above ₹499",
             BannerPlacement.HERO, "url", "/category/fruits-vegetables", 0),
            ("Staples sale", "Up to 20% off on rice, atta and dal",
             BannerPlacement.HERO, "category", "/category/staples-grains", 1),
            ("Use WELCOME100", "Flat ₹100 off on your first order",
             BannerPlacement.STRIP, "coupon", "WELCOME100", 0),
        ]
        for title, subtitle, placement, link_type, target, order in banners:
            defaults = {
                "subtitle": subtitle,
                "placement": placement,
                "link_type": link_type,
                "display_order": order,
            }
            if link_type == "url":
                defaults["link_url"] = target
            elif link_type == "category":
                defaults["linked_category"] = categories["Staples & Grains"]
            elif link_type == "coupon":
                defaults["linked_coupon_code"] = target

            Banner.objects.get_or_create(title=title, defaults=defaults)
        self.stdout.write(f"  banners: {Banner.objects.count()}")
