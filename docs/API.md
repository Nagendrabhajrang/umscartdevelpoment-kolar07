# API Reference

Interactive documentation is generated from the code and always current:

| URL | Format |
|---|---|
| `/api/docs/` | Swagger UI |
| `/api/redoc/` | Redoc |
| `/api/schema/` | OpenAPI 3 YAML |

**121 paths, 191 operations, 160 schemas, 0 schema warnings.**

---

## Conventions

### Base URL

```
https://api.umsmart.com/api/v1/
```

### Identifying the caller (this phase)

```bash
-H "X-Customer-Id: 1"
```

See [`AUTHENTICATION.md`](AUTHENTICATION.md). **There is no authentication in
this phase — do not expose this build publicly.**

### Requests

- JSON bodies (`Content-Type: application/json`)
- File uploads as `multipart/form-data`
- Money as a string with 2 decimals: `"149.00"`
- Timestamps ISO 8601 with offset: `2026-11-09T21:37:58+05:30`

### Responses

Single object:

```json
{ "id": 12, "order_number": "UMS-20261109-4F2A91", "grand_total": "590.00" }
```

List (paginated):

```json
{
  "count": 32,
  "next": "https://api.umsmart.com/api/v1/catalog/products/?page=2",
  "previous": null,
  "results": [ { "id": 49, "name": "Aashirvaad Shudh Chakki Atta" } ]
}
```

Errors — one envelope everywhere:

```json
{
  "error": {
    "code": "insufficient_stock",
    "message": "Only 3 unit(s) of 'Basmati Rice 5kg' are currently in stock.",
    "details": { "product_id": 42, "requested": 10, "available": 3 },
    "status": 409
  }
}
```

`code` is stable and machine-readable; branch on it, never on `message`.

### List query parameters

| Parameter | Applies to | Example |
|---|---|---|
| `page`, `page_size` | all lists | `?page=2&page_size=50` |
| `search` | most lists | `?search=basmati` |
| `ordering` | most lists | `?ordering=-created_at,name` |
| Module filters | per module | `?status=active&brand=Tata` |

### Identifiers in URLs

Every detail route accepts the numeric id, the public UUID **or** the
human-readable number:

```
/api/v1/orders/12/
/api/v1/orders/3f2a9c1e-8b4d-4f7a-9c2e-1d5b7a9e4c61/
/api/v1/orders/UMS-20261109-4F2A91/
```

Support, payments and promotions also accept their reference
(`TKT-…`, `PAY-…`) and coupon codes.

### Status codes

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 204 | Deleted / no content |
| 400 | Validation error or business rule violation |
| 403 | Ownership violation |
| 404 | Unknown resource |
| 405 | Method not allowed on this route |
| 409 | Conflict — duplicate, illegal transition, insufficient stock |
| 500 | Server error (details logged, never returned) |

### Error code catalogue

| Code | Status | Meaning |
|---|---|---|
| `validation_error` | 400 | Field validation failed; `details` names the fields |
| `customer_context_required` | 400 | `X-Customer-Id` header missing |
| `empty_cart` | 400 | Checkout attempted with no items |
| `below_minimum_order_value` | 400 | Cart under the store minimum |
| `max_order_quantity_exceeded` | 400 | Over the per-product cap |
| `store_closed` | 400 | Store closed or in maintenance |
| `store_holiday` | 400 | Today is a store holiday |
| `cod_disabled` | 400 | COD turned off in store settings |
| `product_not_purchasable` | 400 | Product not `active` |
| `invalid_status_transition` | 400 | Unknown status value |
| `invalid_status_transition` | 409 | Illegal order/ticket transition |
| `empty_reply` | 400 | Blank support reply |
| `amount_mismatch` | 400 | COD collected amount ≠ payment amount |
| `refund_exceeds_payment` | 400 | Refund larger than the settled amount |
| `promotion_customer_limit_reached` | 400 | Per-customer usage exhausted |
| `promotion_usage_exhausted` | 400 | Total usage exhausted |
| `invalid_payment_method` | 400 | Not `upi` / `cod` |
| `customer_not_found` | 404 | Header id does not exist |
| `product_not_found` | 404 | Unknown product |
| `order_not_found` | 404 | Unknown order |
| `payment_not_found` | 404 | Unknown or missing payment for an order |
| `address_not_found` | 404 | Unknown address |
| `ticket_not_found` | 404 | Unknown ticket |
| `promotion_not_found` | 404 | Unknown offer or coupon code |
| `banner_not_found` | 404 | Unknown banner |
| `delivery_slab_not_found` | 404 | Unknown slab |
| `duplicate_category` / `duplicate_sku` / `duplicate_barcode` | 409 | Catalogue duplicates |
| `duplicate_mobile_number` / `duplicate_email` | 409 | Customer duplicates |
| `duplicate_coupon_code` | 409 | Coupon code already exists |
| `duplicate_transaction_reference` | 409 | UPI reference already used |
| `duplicate_wishlist_item` | 409 | Product already in the wishlist |
| `insufficient_stock` | 409 | Not enough units |
| `order_not_cancellable` / `order_already_cancelled` | 409 | Cancel refused |
| `ticket_closed` | 409 | Reply to a closed ticket |
| `product_unavailable` | 404 | Soft-deleted product |

---

## Worked examples

### 1. Browse the catalogue

```bash
curl "https://api.umsmart.com/api/v1/catalog/categories/?parent=1"
curl "https://api.umsmart.com/api/v1/catalog/products/?category=3&min_price=50&max_price=200&ordering=-selling_price"
curl "https://api.umsmart.com/api/v1/catalog/products/?search=atta&in_stock=true"
```

Filtering by a **parent** category automatically includes its children.

### 2. Build a cart

```bash
curl -X POST https://api.umsmart.com/api/v1/cart/items/ \
     -H "X-Customer-Id: 1" -H "Content-Type: application/json" \
     -d '{"product": 49, "quantity": 2}'
```

```json
{
  "id": 88, "product": 49, "product_name": "Aashirvaad Shudh Chakki Atta",
  "quantity": 2, "unit_price": "90.00", "line_total": "180.00",
  "stock_available": 42, "is_available": true
}
```

Adding more than the stock returns:

```json
{ "error": { "code": "insufficient_stock", "message": "Only 20 unit(s) of ... are currently in stock.", "details": { "requested": 999, "available": 20 }, "status": 409 } }
```

### 3. Apply a coupon and review totals

```bash
curl -X POST https://api.umsmart.com/api/v1/cart/coupon/ \
     -H "X-Customer-Id: 1" -d '{"code": "FRESH10"}'

curl https://api.umsmart.com/api/v1/cart/summary/ -H "X-Customer-Id: 1"
```

```json
{
  "item_count": 2, "total_quantity": 3,
  "subtotal": "420.00", "discount_amount": "42.00",
  "delivery_charge": "30.00", "packaging_charge": "5.00",
  "tax_amount": "0.00", "grand_total": "413.00",
  "coupon_code": "FRESH10", "is_free_delivery": false,
  "amount_to_free_delivery": "80.00"
}
```

### 4. Checkout with UPI

```bash
curl -X POST https://api.umsmart.com/api/v1/orders/checkout/ \
     -H "X-Customer-Id: 1" -H "Content-Type: application/json" \
     -d '{"address": 1, "payment_method": "upi", "coupon_code": "FRESH10"}'
```

```json
{
  "id": 30, "order_number": "UMS-20261109-4F2A91",
  "status": "pending", "payment_status": "unpaid",
  "subtotal": "420.00", "discount_amount": "42.00",
  "delivery_charge": "30.00", "grand_total": "413.00",
  "payment": {
    "id": 30, "payment_number": "PAY-20261109-77A1B0",
    "method": "upi", "status": "pending"
  },
  "upi_details": {
    "upi_id": "umsmart@okhdfcbank", "payee_name": "UMS Mart",
    "amount": "413.00", "transaction_note": "UMS-20261109-4F2A91",
    "upi_deep_link": "upi://pay?pa=umsmart@okhdfcbank&pn=UMS%20Mart&am=413.00&cu=INR&tn=UMS-20261109-4F2A91"
  }
}
```

### 5. Submit UPI proof, then verify

```bash
# Customer pays in any UPI app, then submits the reference
curl -X POST https://api.umsmart.com/api/v1/payments/30/submit-proof/ \
     -F "transaction_reference=418923456789" \
     -F "proof_image=@screenshot.png"

# Staff approves
curl -X POST https://api.umsmart.com/api/v1/payments/30/approve/ \
     -H "Content-Type: application/json" \
     -d '{"verified_by": "accounts@umsmart.com", "remarks": "Matched in bank statement"}'
```

The order moves to `confirmed` / `paid`. **Every** step is appended to the
verification history:

```bash
curl https://api.umsmart.com/api/v1/payments/30/verifications/
```

```
submitted → resubmitted → approved
```

Rejecting requires a reason and puts the payment back in a resubmittable state:

```bash
curl -X POST https://api.umsmart.com/api/v1/payments/30/reject/ \
     -d '{"reason": "Reference not found in statement", "verified_by": "accounts"}'
```

### 6. Advance an order

```bash
curl -X POST https://api.umsmart.com/api/v1/orders/30/status/ \
     -H "Content-Type: application/json" \
     -d '{"status": "processing", "note": "Picking started", "changed_by": "warehouse"}'
```

Illegal jumps are refused:

```json
{ "error": { "code": "invalid_status_transition", "message": "An order in status 'pending' cannot move to 'delivered'.", "details": { "current_status": "pending", "allowed_next": ["confirmed", "cancelled"] }, "status": 409 } }
```

### 7. Cancel

```bash
curl -X POST https://api.umsmart.com/api/v1/orders/30/cancel/ \
     -H "Content-Type: application/json" \
     -d '{"reason": "customer_request", "note": "Ordered by mistake"}'
```

Stock is restored, the coupon redemption is released and the payment is closed —
all in one transaction.

### 8. Raise a support ticket

```bash
curl -X POST https://api.umsmart.com/api/v1/support/mine/create/ \
     -H "X-Customer-Id: 1" -H "Content-Type: application/json" \
     -d '{"subject": "Missing item", "description": "The milk carton was missing from delivery.", "category": "order_issue", "order": 30}'
```

```json
{ "id": 7, "ticket_number": "TKT-20261109-65CB58", "status": "open", "priority": "medium" }
```

```bash
# staff reply
curl -X POST https://api.umsmart.com/api/v1/support/tickets/7/replies/ \
     -d '{"message": "We are arranging a replacement.", "sender_type": "staff", "sender_name": "priya"}'

# resolve, then rate
curl -X POST https://api.umsmart.com/api/v1/support/tickets/7/status/ -d '{"status": "resolved"}'
curl -X POST https://api.umsmart.com/api/v1/support/tickets/7/rate/   -d '{"rating": 5}'
```

Ticket workflow:

```
open ──► in_progress ──► awaiting_customer ──► resolved ──► closed
  └──────────┴──────────────────┴────────────────┘
```

Illegal moves → `409 invalid_ticket_transition`. Replies to a closed ticket →
`409 ticket_closed`. A customer reply to `awaiting_customer` reopens the ticket
to `in_progress`.

---

## Module reference

### Customers

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/customers/` | list / create |
| GET/PATCH/PUT/DELETE | `/customers/{id}/` | retrieve / update / soft delete |
| GET | `/customers/{id}/orders/` | that customer's orders |
| GET | `/customers/{id}/addresses/` | that customer's addresses |
| GET | `/customers/stats/` | counts by status |
| GET/POST | `/customers/notes/` | internal notes |

Filters: `status`, `city`, `is_active`; search on name/mobile/email.

### Catalog

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/catalog/categories/` | list / create |
| GET/PATCH/DELETE | `/catalog/categories/{id}/` | detail / update / delete |
| GET | `/catalog/categories/tree/` | full nested tree |
| GET | `/catalog/categories/{id}/products/` | products in a category (incl. children) |
| GET/POST | `/catalog/products/` | list / create |
| GET/PATCH/DELETE | `/catalog/products/{id}/` | detail / update / delete |
| GET/POST | `/catalog/products/{id}/images/` | list / upload images |
| GET | `/catalog/products/featured/`, `/low-stock/`, `/filters/` | helpers |

Product filters: `category`, `brand`, `status`, `min_price`, `max_price`,
`in_stock`, `is_featured`; search on name/sku/brand; ordering on price, name,
created_at.

### Inventory

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/inventory/` | stock records (usually one per product) |
| GET/PATCH | `/inventory/{id}/` | detail / update thresholds |
| POST | `/inventory/{id}/add/` | receive stock |
| POST | `/inventory/{id}/remove/` | write off stock |
| POST | `/inventory/{id}/adjust/` | set to an absolute quantity |
| GET | `/inventory/{id}/movements/` | movement history |
| GET | `/inventory/low-stock/`, `/inventory/summary/` | operational views |
| GET | `/inventory/movements/` | global movement log |

Every mutation writes a `StockMovement` with a reason and reference.

### Cart

| Method | Path | Purpose |
|---|---|---|
| GET | `/cart/` | the active cart |
| GET/POST | `/cart/items/` | list / add item |
| PATCH/DELETE | `/cart/items/{id}/` | change quantity / remove |
| GET | `/cart/summary/` | totals, discount, delivery |
| POST/DELETE | `/cart/coupon/` | apply / remove coupon |
| DELETE | `/cart/clear/` | empty the cart |

### Wishlist

`/wishlist/` (mine), `/wishlist/lists/` (+ `/summary/`),
`/wishlist/items/` (+ `{id}/move-to-cart/`), `/wishlist/toggle/`.

### Addresses

`/addresses/` (admin scope, filter by `customer`), `/addresses/mine/`,
`/addresses/mine/add/`, `/addresses/{id}/set-default/`. The first address for a
customer becomes the default automatically; exactly one default is enforced by
a database constraint.

### Orders

| Method | Path | Purpose |
|---|---|---|
| GET | `/orders/` | list (admin) |
| GET | `/orders/{id}/` | detail |
| POST | `/orders/checkout/` | create an order from the cart |
| POST | `/orders/checkout/preview/` | totals and availability **without** creating |
| GET | `/orders/mine/` | caller's orders |
| POST | `/orders/{id}/status/` | advance the lifecycle |
| POST | `/orders/{id}/cancel/` | cancel and restore stock |
| POST | `/orders/{id}/reorder/` | add the items back to the cart |
| GET | `/orders/{id}/history/` | status history |
| GET | `/orders/stats/` | counts and revenue |

Filters: `status`, `payment_status`, `payment_method`, `customer`,
`date_from`, `date_to`; search on order number/mobile.

### Payments

| Method | Path | Purpose |
|---|---|---|
| GET | `/payments/` | list; filter `status`, `method`, `order` |
| GET | `/payments/{id}/` | detail |
| GET | `/payments/order/{order_id}/` | the payment for an order |
| GET | `/payments/{id}/upi-details/` | UPI id, payee, amount, deep link |
| POST | `/payments/{id}/submit-proof/` | transaction reference + screenshot |
| POST | `/payments/{id}/approve/` | verify (marks the order paid and confirmed) |
| POST | `/payments/{id}/reject/` | reject with a mandatory reason |
| GET | `/payments/{id}/verifications/` | this payment's audit trail |
| GET | `/payments/pending-verification/` | work queue for accounts |
| POST | `/payments/{id}/collect-cod/` | record cash received |
| GET/POST | `/payments/refunds/` | refunds |
| GET | `/payments/stats/` | totals by method and status |

### Promotions

`/promotions/` CRUD, lookup by code, `{id}/toggle/`,
`coupons/available/`, `active-offers/`, `summary/`.
Filters: `kind` (`coupon`/`automatic`), `is_active`, `currently_valid`, `code`.

### Banners

`/banners/` CRUD, `live/` (scheduled and active only), `{id}/toggle/`,
`{id}/click/`. Filters: `placement`, `is_active`, `link_type`.

### Support

`/support/mine/`, `/support/mine/create/`, `/support/tickets/` CRUD,
`{id}/replies/`, `{id}/status/`, `{id}/assign/`, `{id}/priority/`,
`{id}/rate/`, `tickets/stats/`, `/support/replies/{id}/`.
Filters: `status`, `category`, `priority`, `mine=1`, `open_only=1`.

### Store settings

| Method | Path | Purpose |
|---|---|---|
| GET/PATCH | `/store-settings/` | singleton configuration |
| POST | `/store-settings/delivery-quote/` | charge for a subtotal |
| GET/POST | `/store-settings/delivery-slabs/` | CRUD |
| GET | `/store-settings/delivery-slabs/resolve/?subtotal=150` | which slab applies |
| GET/POST/PATCH/DELETE | `/store-settings/holidays/` | closed dates |

### Health

```bash
curl https://api.umsmart.com/health/
```

```json
{ "status": "ok", "service": "ums-mart-api", "version": "1.0.0", "database": "up" }
```

Returns non-200 if the database is unreachable, so it is safe for an uptime
monitor and for the deploy script's final gate.
