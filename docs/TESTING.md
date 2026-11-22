# Testing

Everything below was **actually executed** against PostgreSQL 17.11 on
2026-11-09. Numbers are copied from the runs, not estimated.

---

## Results

| Suite | Command | Result |
|---|---|---|
| Django system check | `manage.py check` | 0 issues |
| Production deploy check | `manage.py check --deploy` | 0 issues (with `SECURE_HSTS_PRELOAD=True`) |
| Migrations | `manage.py migrate` | 13 migrations applied |
| Database objects | — | 38 tables, 210 constraints, 270 indexes |
| **Automated tests** | `manage.py test --parallel 4` | **326 passed, 0 failed** |
| **Live smoke suite** | `deployment/scripts/smoke_test.py` | **117 passed, 0 failed** |
| **Front-end contract suite** | `frontend/frontend_e2e.py` | **165 passed, 0 failed** |
| **UI smoke + screenshots** | `frontend/ui_smoke.py both` | **30 shots, 0 errors** |
| OpenAPI schema | `manage.py spectacular` | 0 errors, 0 warnings — 109 paths, 170 operations, 138 schemas |

### Per-module breakdown (automated tests)

| Module | Tests | Covers |
|---|---|---|
| `apps.customers` | 29 | model invariants, CRUD, duplicate mobile/email → 409, notes, stats |
| `apps.catalog` | 47 | category tree, parent/child filtering, product CRUD, sku/barcode duplicates, image upload, search & price filters |
| `apps.inventory` | 28 | stock levels, add/remove/adjust, movement history, cache sync, low-stock |
| `apps.cart` | 40 | add/update/remove, stock caps, quantity caps, delivery slabs, coupon apply/remove, totals |
| `apps.orders` | 44 | checkout, snapshots, stock deduction, coupon redemption, lifecycle, cancel/restore, reorder, overselling |
| `apps.payments` | 30 | UPI proof, duplicate UTR, approve/reject, full history sequence, COD, refunds |
| `apps.promotions` | 37 | discount maths, caps, targeting, eligibility guards, redemption limits, CRUD |
| `apps.store_settings` | 29 | singleton, delivery slabs, quote resolution, holidays, validation |
| `apps.support` | 40 | ticket creation, transitions, replies, reopen, rating, stats |
| `apps.addresses` / `wishlist` / `banners` | 47 | ownership, defaults, duplicate wishlist, move-to-cart, banner lifecycle |
| **Total** | **326** | |

---

## Running the tests

### Automated suite

```bash
cd backend
python manage.py test                                    # everything
python manage.py test apps.orders                       # one module
python manage.py test apps.payments -v 2                # verbose
python manage.py test apps.orders.tests.test_checkout.CheckoutServiceTests
```

The runner creates a real PostgreSQL database (`test_ums_mart_db`), applies
migrations, runs, then drops it. **SQLite is not used anywhere** — the tests
exercise the same constraint and locking behaviour as production.

### End-to-end smoke suite

117 checks over real HTTP across 12 sections, exercising the actual stack:

```bash
cd /path/to/ums_mart
python run_smoke.py
```

Expected tail:

```
SMOKE RESULT: 117 passed, 0 failed
```

It creates its own run-scoped fixtures (`RUN_TOKEN`) and cleans up afterwards,
so it can be run repeatedly against a live database.

---

## What the tests actually assert

### Models and relationships

- Category tree: parent/child links, cycle rejection, cascade rules
- Product → category, product → stock one-to-one
- Order → items → product, with `PROTECT` on the product FK
- One default address per customer (enforced by a DB constraint, asserted)
- Unique constraints on sku, barcode, mobile, email, coupon code, UTR
- `full_clean()` in `save()` rejects duplicates before the DB does

### CRUD and status codes

Every module asserts the full matrix: 200 read, 201 create, 200 update, 204
delete, 404 after delete, 400 on bad input, 405 on disallowed methods.

### Serializer validation

Negative prices, zero quantities, over-100 percentages, backwards date ranges,
bad pincodes, malformed coupon codes, blank required fields, invalid enum
values — each asserted to return 400 **with the offending field**.

### Duplicates

Asserted as **409 with a specific code**, not a generic 400:
`duplicate_category`, `duplicate_sku`, `duplicate_barcode`,
`duplicate_mobile_number`, `duplicate_email`, `duplicate_coupon_code`,
`duplicate_transaction_reference`, `duplicate_wishlist_item`.

This required a real fix: DRF's auto `UniqueValidator` fires *before* a
custom `validate_<field>`, producing 400. The serializers now clear that
validator (`extra_kwargs = {"field": {"validators": []}}`) so the custom check
can answer with the correct status and code.

### Stock validation and overselling

- Adding more than available → `409 insufficient_stock`
- Adding more than `max_order_quantity` → `400 max_order_quantity_exceeded`
- **Stock is checked before the quantity cap**, so a customer sees "only 3
  left" rather than a policy limit (found by a failing test, then fixed)
- Checkout with another buyer taking the stock in between → `409`, and
  **`Order.objects.count() == 0`** — proving the transaction rolled back
- Cancel restores exactly the ordered quantity and writes a `RETURN` movement

### Checkout and order creation

- price, product name and address are **snapshots** — asserted by mutating the
  product and address afterwards and re-reading the order
- cart becomes `converted` and is emptied; a second checkout → `400 empty_cart`
- coupon redemption recorded, `used_count` incremented, released on cancel
- COD → `cod_due`; UPI → `unpaid` + `upi_details.upi_deep_link`
- below minimum order, closed store, disabled COD → specific 400 codes

### Payment verification

The full audit sequence is asserted verbatim:

```python
[
  "submitted",     # first proof
  "submitted",     # proof after rejection
  "rejected",
  "resubmitted",
  "approved",
]
```

Plus: duplicate UTR across payments → 409; approve without a reference → 400;
double approve → 409; reject without a reason → 400; COD collected twice → 409;
refund above the settled amount → 400; cancelling an order closes an unpaid
payment.

### Transaction handling

- A failed checkout leaves no order, no stock movement and no coupon consumption
- A double-submitted checkout creates exactly one order
- Stock cache invalidation: `product.stock.quantity` reflects the service's
  write on the caller's instance (this was a real bug — the service loaded its
  own instance, leaving the caller's cached reverse one-to-one stale)
- Cancelling twice restores stock **once** and the second call → 409

### Support workflow

- every legal transition, and `409 tiny_ticket_transition` for every illegal one
- customer reply to `awaiting_customer` reopens to `in_progress`
- replies to a closed ticket → `409 ticket_closed`
- `reply_count` is recounted from the database so it cannot drift

---

## Bugs the tests found (and fixed)

Keeping this list is deliberate: these are the failures that only appeared
because the tests ran against real PostgreSQL with real HTTP.

| Bug | Symptom | Fix |
|---|---|---|
| Stale product stock cache | `product.stock.quantity` unchanged after `add_stock` | write `_state.fields_cache["stock"]` on both instances |
| Nested image upload rejected | `product` reported required on `/products/{id}/images/` | clear the validator, re-assert requiredness only on the standalone route |
| Parent category filter returned nothing | children not included | resolve descendants in the filter |
| Duplicate SKU returned 400 | auto `UniqueValidator` pre-empted the custom check | clear `validators=[]`, answer 409 |
| Duplicate coupon returned 400 | same | same |
| Percentage > 100 accepted on PATCH | `StoreSettingsUpdateSerializer` had no cross-field validation | added `validate()` |
| Both payment methods could be disabled | same | same |
| `cancel_order` didn't refresh its caller's instance | stale status read after cancel | sync fields back to the passed instance |
| Double cancel succeeded | no state re-check under lock | re-read `select_for_update()`, reject `cancelled` |
| Ticket self-transition silently accepted | `closed → closed` returned 200 | raise `409 invalid_ticket_transition` |
| `reply_count` drifted | opening description double-counted | recount from the DB |
| Coupon-code lookup 404'd | `lookup_value_regex` rejected letters | widened to `[A-Za-z0-9_-]{1,64}` |
| `PaymentVerification` undefined in schema | missing import | imported; schema warnings now 0 |

---

## Not tested (and why)

| Item | Reason |
|---|---|
| Authentication / OTP / RBAC | Not implemented in this phase (scope decision) |
| Real UPI settlement | No gateway by requirement; verification is manual by design |
| SMS / email delivery | No provider configured; email uses the console backend locally |
| Load / concurrency benchmarks | Row locking is asserted functionally, not benchmarked |
| Hostinger VPS provision, DNS, Let's Encrypt, systemd startup | Requires a live server — the guide is instructions, not a claim |

The Gunicorn + Nginx + PostgreSQL stack **was** run locally and verified
end-to-end (TLS, redirect, proxy, static 404s, security headers, `/health/`,
`/api/v1/`, docs). An actual VPS deployment was not performed.
