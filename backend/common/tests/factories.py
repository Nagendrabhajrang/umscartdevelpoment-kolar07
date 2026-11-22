"""Shared object builders for the test-suite.

Plain helper functions (no factory_boy dependency) so the test suite stays
trivial to install and run on a fresh machine.
"""

from decimal import Decimal

from apps.addresses.models import Address, AddressLabel
from apps.catalog.models import Category, Product, UnitType
from apps.customers.models import Customer
from apps.inventory.services import add_stock, set_initial_stock
from apps.orders.models import Order, OrderItem, PaymentMethod, OrderStatus
from apps.store_settings.models import DeliverySlab, StoreSettings


def make_store(**overrides):
    settings_obj = StoreSettings.load()
    defaults = {
        "store_name": "UMS Mart",
        "delivery_charge": Decimal("40.00"),
        "free_delivery_threshold": Decimal("500.00"),
        "minimum_order_value": Decimal("0.00"),
        "default_tax_percent": Decimal("0.00"),
        "packaging_charge": Decimal("0.00"),
        "delivery_eta_minutes": 45,
        "cod_enabled": True,
        "upi_enabled": True,
        "upi_id": "umsmart@okhdfcbank",
        "upi_payee_name": "UMS Mart",
        "is_store_open": True,
        "order_prefix": "UMS",
    }
    defaults.update(overrides)
    for field, value in defaults.items():
        setattr(settings_obj, field, value)
    settings_obj.save()
    return settings_obj


def make_customer(**overrides):
    counter = Customer.all_objects.count() + 1
    defaults = {
        "full_name": f"Test Customer {counter}",
        "mobile_number": f"+91900000{counter:04d}",
        "email": f"customer{counter}@example.com",
    }
    defaults.update(overrides)
    return Customer.objects.create(**defaults)


def make_category(**overrides):
    counter = Category.objects.count() + 1
    defaults = {"name": f"Test Category {counter}"}
    defaults.update(overrides)
    return Category.objects.create(**defaults)


def make_child_category(parent=None, **overrides):
    counter = Category.objects.count() + 1
    defaults = {"name": f"Test Child Category {counter}", "parent": parent}
    defaults.update(overrides)
    return Category.objects.create(**defaults)


def make_product(category=None, quantity: int = 100, **overrides):
    category = category or make_category()
    counter = Product.all_objects.count() + 1
    defaults = {
        "name": f"Test Product {counter}",
        "category": category,
        "mrp": Decimal("100.00"),
        "selling_price": Decimal("80.00"),
        "unit_type": UnitType.PIECE,
        "unit_value": Decimal("1.00"),
    }
    defaults.update(overrides)
    product = Product.objects.create(**defaults)
    set_initial_stock(product, quantity=0)
    if quantity:
        add_stock(product, quantity, reference="TEST", reason="Test stock")
    return product


def make_address(customer, **overrides):
    defaults = {
        "label": AddressLabel.HOME,
        "recipient_name": customer.full_name,
        "recipient_mobile": customer.mobile_number,
        "line1": "1 Test Street",
        "line2": "Test Area",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560001",
    }
    defaults.update(overrides)
    # Honour the "one default address per customer" rule: only the first
    # address for a customer becomes the default.
    if "is_default" not in overrides:
        defaults["is_default"] = not Address.objects.filter(
            customer=customer, is_default=True
        ).exists()
    return Address.objects.create(customer=customer, **defaults)


def make_delivery_slab(**overrides):
    counter = DeliverySlab.objects.count() + 1
    defaults = {
        "name": f"Slab {counter}",
        "min_order_value": Decimal("0.00"),
        "max_order_value": Decimal("199.99"),
        "delivery_charge": Decimal("30.00"),
    }
    defaults.update(overrides)
    return DeliverySlab.objects.create(**defaults)


def make_order(customer, address=None, items=None, payment_method=PaymentMethod.COD,
               status=OrderStatus.PENDING, **overrides):
    """Create an order directly in the DB (bypassing checkout)."""
    address = address or make_address(customer)
    items = items or []
    subtotal = sum((item["unit_price"] * item["quantity"] for item in items), Decimal("0"))
    order = Order.objects.create(
        customer=customer,
        address=address,
        delivery_recipient_name=address.recipient_name,
        delivery_recipient_mobile=address.recipient_mobile,
        delivery_address_line1=address.line1,
        delivery_address_line2=address.line2,
        delivery_city=address.city,
        delivery_state=address.state,
        delivery_pincode=address.pincode,
        status=status,
        payment_method=payment_method,
        subtotal=subtotal,
        grand_total=subtotal,
        item_count=len(items),
        total_quantity=sum(item["quantity"] for item in items),
        **overrides,
    )
    for item in items:
        OrderItem.objects.create(
            order=order,
            product=item["product"],
            product_name=item["product"].name,
            product_sku=item["product"].sku,
            quantity=item["quantity"],
            unit_mrp=item["product"].mrp,
            unit_price=item["unit_price"],
            line_total=item["unit_price"] * item["quantity"],
        )
    return order
