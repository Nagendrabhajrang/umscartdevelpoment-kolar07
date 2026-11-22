# Architecture

## Why a modular monolith

The store has twelve tightly coupled domains that share one database and one
deployment. Splitting them into services would add network failure modes,
distributed transactions and operational overhead for no benefit at this scale.
A monolith with **real module boundaries** keeps transactions simple and
ACID guarantees intact, while remaining extractable later.

The discipline that makes this work is the layering rule below. It is not
aspirational — it is enforced by the shape of the code and by the tests.

---

## Layering

```
                    ┌─────────────────────────────┐
   HTTP request ───►│  urls.py                    │  routing only
                    └─────────────┬───────────────┘
                                  ▼
                    ┌─────────────────────────────┐
                    │  views.py                   │  parse → validate →
                    │  (thin)                     │  call service → serialize
                    └─────────────┬───────────────┘
                        ┌─────────┴─────────┐
                        ▼                   ▼
            ┌───────────────────┐   ┌───────────────────┐
            │  serializers.py   │   │  services.py      │  writes + rules
            │  validation       │   │  transactions     │
            └───────────────────┘   └─────────┬─────────┘
                                              ▼
                                    ┌───────────────────┐
                                    │  selectors.py     │  read queries
                                    └─────────┬─────────┘
                                              ▼
                                    ┌───────────────────┐
                                    │  models.py        │  constraints,
                                    │                   │  indexes, properties
                                    └───────────────────┘
```

### Rules

1. **Views are thin.** A view validates input, calls exactly one service or
   selector, and serializes the result. No ORM writes, no business rules, no
   arithmetic.
2. **Services own writes.** Every state change is a `@transaction.atomic`
   function that enforces the invariants and logs what it did.
3. **Selectors own reads.** Query composition (joins, annotations, filtering)
   lives here so views and other services share one implementation.
4. **Serializers validate shape, services validate meaning.** "Is `quantity` a
   positive integer?" is a serializer concern. "Is there enough stock?" is a
   service concern.
5. **A module may call another module's service or selector — never its
   models directly from a view.** Cross-module writes are orchestrated by the
   owning service (checkout calls inventory and promotions services).
6. **No module imports a view or serializer from another module.**

A useful check when reviewing a diff: if a `views.py` gained more than a few
lines of logic, it belongs in a service.

---

## Shared foundation (`common/`)

### Model mixins

| Mixin | Provides |
|---|---|
| `BaseModel` | integer PK, public `uid` (UUID), `created_at`, `updated_at` |
| `UUIDPrimaryKeyModel` | UUID PK where an integer id would leak volume |
| `SoftDeleteModel` | `is_deleted`/`deleted_at`, `.objects` (live only), `.all_objects`, `hard_delete()` |
| `PublishableModel` | `is_active`, `is_featured`, display ordering |
| `SluggedModel` | unique slug derivation |

Why both an integer PK **and** a UUID: integers are fast for joins and readable
in the admin; the `uid` is what the API exposes when an id should not be
guessable or countable. Human-facing documents use a third form
(`UMS-20261109-4F2A91`), which is what customers quote to support.

### Error handling

Exception → HTTP mapping happens in one place
(`common/exceptions.py` + `common/middleware.py`):

```python
class BusinessRuleError(APIException):      status_code = 400
class ConflictError(BusinessRuleError):     status_code = 409
class ResourceNotFoundError(APIException):  status_code = 404
class EmptyResourceError(BusinessRuleError):status_code = 400
class InsufficientStockError(ConflictError):status_code = 409
```

Every error carries a stable machine-readable `code`. The smoke suite asserts
those codes, which is what stops a refactor from silently changing the contract.

### Identity seam

```python
# common/identity.py
def resolve_customer(request) -> Customer:
    ...prefers the session's customer, falls back to X-Customer-Id for guests...
```

Every customer-scoped view calls this and nothing else. There is exactly one
line to change when authentication lands, and no view has to be touched. See
[`AUTHENTICATION.md`](AUTHENTICATION.md).

---

## Transaction and concurrency strategy

The failure this design exists to prevent: two customers buying the last unit
of stock, both getting an order confirmation, one of them never being served.

### Checkout, step by step

```python
@transaction.atomic
def checkout(customer, address, payment_method, coupon_code=None):
    cart = lock_cart(customer)                   # SELECT ... FOR UPDATE
    items = revalidate_lines(cart)               # live price + availability
    for item in items:
        stock = lock_stock(item.product)         # SELECT ... FOR UPDATE
        assert_enough(stock, item.quantity)      # raises -> whole tx rolls back
        stock.quantity -= item.quantity
        stock.save(update_fields=["quantity"])
        StockMovement.objects.create(type=SALE, ...)
    order = create_order_with_snapshots(...)     # prices frozen here
    apply_coupon(order, coupon_code)             # increments usage atomically
    cart.convert_to(order)                       # cart can never be reused
    create_payment(order, payment_method)
    write_status_history(order, PENDING)
    return order
```

Properties this buys:

- **No overselling.** The stock row is locked before it is read for the
  decision, so a concurrent checkout blocks until the first commits and then
  sees the reduced quantity.
- **No partial orders.** If any line fails, the entire transaction rolls back —
  no order, no stock movement, no coupon consumption, cart still intact.
- **Exactly-once conversion.** The cart row is locked and then marked
  `converted`; a double-click on "Place order" cannot create two orders.
- **Immutable history.** `OrderItem.unit_price`, `product_name` and the
  delivery address fields are copies, not foreign keys. Repricing a product or
  editing an address months later cannot rewrite what a customer was charged.

### Where locks are taken

| Operation | Lock | Why |
|---|---|---|
| Checkout | cart row, then each stock row (ordered by product id) | prevents double conversion and lost updates |
| Cancel order | order row | prevents double cancel and double stock restore |
| Payment approve/reject | payment row | prevents an approval racing a resubmission |
| Coupon redeem | promotion row | keeps `used_count` exact under concurrency |
| Stock adjust | stock row | keeps `quantity` and its history consistent |

Lock ordering is consistent (always ascending by primary key) so two concurrent
checkouts cannot deadlock against each other.

### Isolation

PostgreSQL's default `READ COMMITTED` is sufficient because every decision that
depends on a value is made **after** the row is locked. Raising the level
globally would add serialization failures without buying correctness here.

---

## Money

- Always `DecimalField(max_digits=12, decimal_places=2)` — never `float`.
- Rounding goes through `common.utils.round_money()` (`ROUND_HALF_UP`) at the
  boundary where a value becomes customer-visible.
- Tax, delivery and discount are computed in a fixed order so the same cart
  always produces the same total:

```
subtotal      = Σ(unit_price × quantity)
discount      = promotion engine (never exceeds subtotal)
taxable       = subtotal − discount
tax           = taxable × tax_percent / 100
delivery      = slab / flat / free per store settings
packaging     = store settings
grand_total   = taxable + tax + delivery + packaging
```

`checkout/preview/` and the cart summary call the same function, so a quoted
total can never disagree with the created order.

---

## Module dependencies

Dependencies flow one way. Arrows point at the module being called.

```
orders ──► cart ──► catalog
   │        │          ▲
   │        └──► inventory
   ├──► promotions
   ├──► payments
   ├──► addresses
   └──► store_settings

support ──► orders, customers
banners ──► catalog
wishlist ──► catalog, cart
```

No cycles. `catalog` knows nothing about carts; `payments` knows about orders
only through the FK and the status contract.

---

## Database design conventions

- Foreign keys: meaningful `on_delete` (`PROTECT` for financial history,
  `CASCADE` for owned children, `SET_NULL` for optional references).
- `CheckConstraint`s enforce invariants the database can prove
  (`quantity >= 0`, `amount > 0`, `end_date > start_date`).
- Unique constraints back every application-level uniqueness rule.
- Indexes exist for real query patterns: foreign keys, `slug`, `status`,
  `created_at` on list endpoints, and composite `(parent, display_order)`.
- `full_clean()` runs in `save()` on the models whose invariants must hold
  regardless of entry point, so the admin cannot create what the API rejects.
- Every list endpoint paginates; no endpoint can return an unbounded set.

**Verified:** 38 tables, 210 constraints, 270 indexes in PostgreSQL 17.11.

---

## Extension points

| Need | Where |
|---|---|
| Authentication | implement `common/identity.resolve_customer()` |
| Permissions/RBAC | `common/permissions.py`, already wired into every view |
| SMS/OTP provider | new `apps/notifications/`, called from services |
| Payment gateway (later) | new service beside the UPI one; the `Payment` model already models provider references |
| Object storage for media | change `DEFAULT_FILE_STORAGE` + the Nginx `/media/` block |
| Async work (emails, invoices) | Celery beside the existing services; nothing in the request path needs to move |
| Read replicas | `selectors.py` is already the single read path |
