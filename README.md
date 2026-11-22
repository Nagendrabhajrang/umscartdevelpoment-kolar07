<<<<<<< HEAD
# umscartdevelpoment-kolar07
project
=======
# UMS Mart — Online Grocery Store

A complete grocery-commerce system: a **Django REST API** on PostgreSQL and two
**React** front ends — a customer storefront and a staff admin console.

The backend is a **modular monolith**: every module owns its models, business
logic, API surface and tests. Views stay thin; business rules live in service
layers; reads go through selectors.

| App | Stack | Runs on |
|---|---|---|
| **API** | Django 5 + DRF + PostgreSQL 17 | `http://127.0.0.1:8000` |
| **Customer storefront** | React 18 + Vite + Tailwind | `http://127.0.0.1:5173` |
| **Admin console** | React 18 + Vite + Tailwind | `http://127.0.0.1:5174` |

---

## Highlights

| | |
|---|---|
| **11 business modules** | customers, catalog, inventory, cart, wishlist, addresses, orders, payments, promotions, banners, store settings |
| **REST API** | versioned at `/api/v1/`, 109 paths / 170 operations / 138 schemas |
| **Two front ends** | customer storefront (15 routes) and admin console (13 routes), both React 18 + Vite + Tailwind |
| **Payments** | Cash on delivery only — cash recorded on delivery, full audit trail, refunds. No gateway, no UPI |
| **Concurrency safe** | `select_for_update()` row locking, atomic transactions, race-proof get-or-create — stock cannot oversell, carts/wishlists cannot 500 under load |
| **API docs** | OpenAPI 3 schema, Swagger UI and Redoc, zero schema warnings |
| **Tests** | 326 Django tests + a 117-check live smoke suite + a 165-check front-end contract suite + 30 screenshot regression shots |
| **Deployment** | Gunicorn + Nginx + systemd + Let's Encrypt, with deploy and backup scripts |

### Verified, not assumed

| Check | Result |
|---|---|
| `manage.py check` (dev + production) | 0 issues, both |
| Migrations against PostgreSQL 17.11 | 13 applied, 38 tables |
| Django test suite | **326 passed, 0 failed** |
| Live smoke suite against a running API | **117 passed, 0 failed** |
| Front-end contract suite (`frontend_e2e.py`) | **165 passed, 0 failed** |
| UI smoke + screenshots (Playwright) | **30 shots, 0 console / page / network errors** |
| `npm run build` (both apps) | exit 0, 0 warnings |
| OpenAPI schema generation | 0 errors, 0 warnings |
| Concurrency probes (8 threads × 4 rounds) | cart 32/32 `200`, wishlist 24/24 `200` |
| Gunicorn + Nginx + TLS stack | served real requests successfully |
| Backup → restore round trip | verified with `pg_restore` |

---

## Architecture

### Request flow

```
HTTP request
   │
   ▼
urls.py ──► views.py        thin: validate → call service → serialize
                │
                ├──► serializers.py   input validation, representation
                ├──► services.py      business rules, transactions, locking
                └──► selectors.py     read-only query composition
                        │
                        ▼
                     models.py        constraints, indexes, invariants
```

A view never touches the ORM for writes and never contains business rules. A
service never renders a response. That separation is what keeps a modular
monolith from decaying into a monolith.

### Module map

| Module | Responsibility |
|---|---|
| `customers` | Customer profiles, addresses relation, notes, status |
| `catalog` | Parent/child categories, products, product images, search & filters |
| `inventory` | Stock levels, reservations, full movement history |
| `cart` | Active cart, line items, live totals, coupon application |
| `wishlist` | Named wishlists, toggle, move-to-cart |
| `addresses` | Delivery addresses, one default per customer |
| `orders` | Checkout, order lifecycle, cancellation, reorder, returns |
| `payments` | Cash recording, verification audit trail, refunds (UPI retired) |
| `promotions` | Coupons and automatic offers, eligibility engine, redemption limits |
| `banners` | Homepage/banner placements with scheduling |
| `store_settings` | Singleton config, delivery slabs, holidays, business hours |

### Front ends

Two independent Vite apps share the same API but no code, so the storefront can
be shipped to customers without exposing admin screens.

**`frontend/customer-web/`** — 15 routes: home, categories, product listing,
product detail, search, cart, wishlist, checkout, order list + detail, profile,
addresses, help & contact, login placeholder, 404. Mobile-first; the storefront is
designed at 390 px first and scales up.

**`frontend/admin-dashboard/`** — 13 routes: dashboard, orders (+detail),
payments, products, categories, inventory, customers (+detail), promotions,
banners, settings. Desktop-first dense tables, with modals for every
create/edit form.

Both talk to the API through a thin `services/` layer — one module per backend
module, so an endpoint change is a one-line edit. Money, dates and enum labels
are formatted by shared helpers, and every enum value in both apps was diffed
against the generated OpenAPI schema.

The storefront identifies the shopper with `X-Customer-Id` and a "who am I"
switcher in the header; the admin console has **no login** and says so in a
"No auth" chip. See [Authentication](#authentication--deliberately-absent-in-this-phase).

### Shared foundation (`common/`)

- **Models** — `BaseModel` (integer PK + public UUID + timestamps), `SoftDeleteModel`, `PublishableModel`, `SluggedModel`
- **Errors** — typed exceptions (`BusinessRuleError`, `ConflictError`, `ResourceNotFoundError`, `EmptyResourceError`, `InsufficientStockError`) mapped to a single JSON envelope
- **Pagination, filters, validators, permissions, middleware, logging**
- **Identity seam** — `common.identity.resolve_customer()` is the single place a caller is identified. It prefers the authenticated session's customer and falls back to `X-Customer-Id` for anonymous callers.

### Consistent error envelope

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

| Status | Used for |
|---|---|
| 400 | Validation failure, business rule, empty cart |
| 401 / 403 | Reserved — authentication phase, and ownership violations |
| 404 | Unknown resource (`*_not_found`) |
| 409 | Duplicate, illegal state transition, insufficient stock, stale version |
| 422 | Reserved for future use |
| 500 | Unhandled error (details logged, never leaked) |

---

## Business logic worth knowing

### Checkout and overselling

`POST /api/v1/orders/checkout/` runs in a single transaction:

1. Lock the cart row (`SELECT … FOR UPDATE`)
2. Re-validate every line against live stock
3. Lock and decrement each `Stock` row
4. Write a `StockMovement(type=SALE)` per line
5. Create the order with **price and address snapshots** (history cannot be rewritten by later edits)
6. Redeem the coupon, incrementing usage counters atomically
7. Mark the cart `converted` and create the payment record
8. Write the first `OrderStatusHistory` row

Two concurrent checkouts of the last unit cannot both succeed; the loser gets
`409 insufficient_stock` and its transaction rolls back completely.

### Order lifecycle

```
pending ──► confirmed ──► processing ──► packed ──► out_for_delivery ──► delivered ──► returned ──► refunded
   │            │              │
   └────────────┴──────────────┴──────► cancelled
```

Only transitions in `ALLOWED_TRANSITIONS` are permitted; anything else returns
`409 invalid_status_transition`. Cancelling restores stock, releases the coupon
redemption and closes the payment. A second cancel returns
`409 order_already_cancelled`.

### Cash on delivery

The only payment method. It is deliberately simple and auditable:

1. Checkout creates the order with `payment_status=cod_due` and a `Payment`
   row with `payment_status=pending`
2. The rider collects the cash at the door; staff record it via
   `POST /payments/{id}/cod-collected/`
3. That sets `payment_status=paid`, stamps `paid_at`, and moves the order to
   `cod_collected`
4. Every step appends an immutable `PaymentVerification` row — the audit trail
   is the product, not an afterthought

The `Payment` model carries the agreed fields: `id`, `order`, `customer`,
`payment_method`, `transaction_id`, `amount`, `payment_status`,
`payment_proof`, `upi_id`, `verified_by`, `verified_at`, `rejection_reason`,
`paid_at`, `created_at`, `updated_at`. `transaction_id` and `upi_id` stay in
the schema (blank for cash) so a future UPI phase needs no migration.

**UPI is disabled, not deleted.** `/upi-details/`, `/submit-proof/`,
`/approve/` and `/reject/` return `400 upi_not_enabled` rather than pretending
to work, and a `payment_method=upi` checkout is rejected by the serializer.

**Delivery requires payment.** The admin console disables "Mark as delivered"
until `payment_status` is `paid` / `cod_collected` — so a product can never be
handed over with the money still outstanding.

### Discounts

`promotions.services.evaluate_coupon()` is a pure function over cart items:

- percentage (with optional cap), fixed amount, free delivery
- scope: all items, one category, or specific products
- guards: minimum order value, minimum item count, first-order-only, per-customer
  limit, total usage limit, validity window, active/visible flags
- automatic (code-less) offers are evaluated by priority; the best one wins
- usage counters are incremented inside the checkout transaction and released
  on cancellation

### Delivery charges

Resolved by `store_settings.services.calculate_delivery_charge()`:

1. Free above `free_delivery_threshold`
2. Otherwise the most specific active `DeliverySlab` covering the subtotal
3. Otherwise the flat `delivery_charge`

The same function powers the checkout preview, the cart summary and
`POST /store-settings/delivery-quote/`, so a quote shown in the cart can never
disagree with the order total.

---

## Quick start (local development)

> **New to this?** Start with [`SETUP_GUIDE.md`](SETUP_GUIDE.md) — the complete
> walkthrough from installing Python/Node/PostgreSQL to a running store, with a
> troubleshooting table. [`RUN.md`](RUN.md) is the shorter version.

### Prerequisites

- Python 3.11+ (developed on 3.13)
- PostgreSQL 14+ (developed on 17.11) — **SQLite is not supported**

### 1. Database

```bash
sudo -u postgres psql
```

```sql
CREATE ROLE ums_mart_user WITH LOGIN PASSWORD '1234' CREATEDB;
CREATE DATABASE ums_mart_db OWNER ums_mart_user;
```

### 2. Environment

```bash
cd ums_mart
cp .env.example backend/.env
```

Edit `backend/.env`:

```ini
DJANGO_SETTINGS_MODULE=config.settings.development
DEBUG=True
DJANGO_SECRET_KEY=dev-only-secret-key-change-me
DB_NAME=ums_mart_db
DB_USER=ums_mart_user
DB_PASSWORD=1234
DB_HOST=127.0.0.1
DB_PORT=5432
TIME_ZONE=Asia/Kolkata
```

### 3. Install and run

```bash
cd backend

python -m venv ../venv
source ../venv/bin/activate            # Windows: ..\venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_data             # optional demo catalogue
python manage.py createsuperuser       # for /admin/
python manage.py runserver
```

On Windows the same commands work in PowerShell/cmd; only the activation path
differs. Nothing in the codebase is POSIX-specific.

### 4. Front ends

```bash
cd frontend/customer-web     && npm install && npm run dev    # :5173
cd frontend/admin-dashboard  && npm install && npm run dev    # :5174
```

Both dev servers proxy `/api` and `/media` to `http://127.0.0.1:8000`, so the
apps work with no CORS configuration at all. To point an app at a different
backend, set `VITE_API_BASE_URL` (default `/api/v1`); then list the origin you
serve in `CORS_ALLOWED_ORIGINS` in `backend/.env` — `5173` and `5174` are
pre-listed there.

Production builds are plain static files, so they deploy behind the same Nginx
that proxies `/api/`:

```bash
npm run build      # -> dist/
```

### 5. Explore

| URL | What |
|---|---|
| http://127.0.0.1:8000/ | Landing page — live counts, health, endpoint index |
| http://127.0.0.1:8000/api/v1/ | API root (JSON index) |
| http://127.0.0.1:8000/api/docs/ | Swagger UI |
| http://127.0.0.1:8000/api/redoc/ | Redoc |
| http://127.0.0.1:8000/api/schema/ | OpenAPI 3 YAML |
| http://127.0.0.1:8000/admin/ | Django admin |
| http://127.0.0.1:8000/health/ | Health + DB status |

---

## Authentication

Authentication is implemented as a self-contained module under
`backend/apps/authentication/`. Full reference, including request and response
bodies for every endpoint, is in
[`backend/docs/authentication_api.md`](backend/docs/authentication_api.md).

**Two separate login workflows, never mixed:**

| | Admin | Customer |
|---|---|---|
| Credential | username + password | mobile number |
| Second factor | 6-digit code by email | 6-digit code by SMS |
| Account origin | `manage.py create_admin` only | auto-created on first successful OTP |
| Prefix | `/api/admin/` | `/api/customer/` |

No token is issued until the second factor is verified. Backend selection is
automatic: Resend (or console) for email, 2Factor.in for SMS.

**Enforced server-side:**

- exactly one admin exists, and there is no public admin registration endpoint
- one active session per user — a new login revokes the previous one
- OTPs are hashed, single-use, expire in 5 minutes, resend after 60 seconds,
  5 attempts, capped per account and per IP
- role checks run on the server, read from the account row — a client cannot claim a role
- password reset deletes every session row, so old cookies stop working at once
- forgot-password returns an identical response whether or not the address is known

Django sessions (round 30; JWT was removed entirely). The credential is an
HttpOnly `ums_mart_sessionid` cookie backed by a `django_session` row, valid for
seven days with `SESSION_EXPIRE_AT_BROWSER_CLOSE = False`. Nothing is stored in
localStorage but a display summary, and every request re-checks that the session is still
active, so logout and password resets take effect immediately rather than at
token expiry.

### Signing in

Both apps have real login screens wired to this API.

| App | Route | Flow |
|---|---|---|
| Storefront (:5173) | `/login` | mobile → SMS code → session |
| Dashboard (:5174) | `/login` | username + password → emailed code → session |

Signed out, the storefront lets anyone browse the catalogue, cart and wishlist.
`/orders`, `/checkout`, `/profile` and `/addresses` redirect to `/login` and
return you to the page you asked for. The dashboard redirects everything except
`/login`.

**How a session reaches the commerce data.** `common/identity.py` resolves the
acting customer from the bearer token first, falling back to the `X-Customer-Id`
header only when no token is present. So a signed-in shopper's cart, orders and
addresses are theirs by construction - editing the header cannot reach another
account. The fallback is retained because the `/api/v1/...` routes have not been
switched to require authentication; **those routes are still open to an
unauthenticated caller who names a customer id**, so do not expose a deployment
to the public internet yet.

These routes *are* protected: `/api/admin/`, `/api/customer/` and `/api/auth/`.
Everything under them rejects a missing, expired, or revoked token.

```bash
# provision the single admin account (no other way to create one)
python manage.py create_admin --username admin \
  --email nagendrajoe@gmail.com --password 'UMSMart@Admin2026'
```

For local development, `.env` may set `AUTH_DEV_MODE=True` so auth responses
echo the code as `dev_otp`. It is ignored whenever `DEBUG=False`, so a
production deployment cannot leak codes even if the variable is left set.

---

## API surface

Full interactive documentation at `/api/docs/`. Summary:

| Module | Base path | Notes |
|---|---|---|
| Customers | `/api/v1/customers/` | CRUD, search, notes, stats |
| Catalog | `/api/v1/catalog/{categories,products}/` | parent/child categories, images, search, price/brand filters |
| Inventory | `/api/v1/inventory/stock/` | stock CRUD, `add`/`remove`/`adjust`, `summary/`, `low-stock/`, movement history |
| Cart | `/api/v1/cart/` | current cart, items, summary, coupon apply/remove, clear |
| Wishlist | `/api/v1/wishlist/` | lists, items, toggle, move-to-cart |
| Addresses | `/api/v1/addresses/` | CRUD, `mine/`, `set-default` |
| Orders | `/api/v1/orders/` | `checkout/`, `checkout/preview/`, `mine/`, `{id}/status/`, `{id}/cancel/`, `{id}/reorder/`, `stats/` |
| Payments | `/api/v1/payments/` | `order/{id}/`, `cod-collected/`, `verifications/`, `stats/`, refunds |
| Promotions | `/api/v1/promotions/` | CRUD, `coupons/available/`, `active-offers/`, `summary/`, lookup by code |
| Banners | `/api/v1/banners/` | CRUD, `live/`, `toggle/`, `click/` |
| Store settings | `/api/v1/store-settings/` | singleton config, `delivery-slabs/`, `delivery-quote/`, `holidays/` |

Conventions across every module: pagination, `?search=`, module-specific
filters, `?ordering=`, duplicate conflicts as `409`, human-readable ids
(`UMS-…`, `PAY-…`, `TKT-…`) accepted in URLs alongside numeric ids and UUIDs.

---

## Demo data

`python manage.py seed_data` builds a store you can demo immediately — and it is
idempotent, so re-running it repairs rather than duplicates.

| What | How much |
|---|---|
| Store settings | name, contact phone/email/address, delivery slabs, hours, holidays |
| Categories | 20 (parent + child) |
| Products | 32, with generated artwork at 4 sizes |
| Stock | one row per product, seeded quantities |
| Customers | 4 demo shoppers with addresses |
| Promotions | coupons (`WELCOME100`, `FRESH10`, `FREESHIP`) + automatic offers |
| Orders | 16 across 4 customers, in 8 different states |
| Payments | 16 — all COD: 12 collected (`paid`), 4 due (`pending`) |

Notes worth trusting:

- **Artwork is generated, not downloaded.** Each product, category and banner
  gets a PNG (initials chip + unit subtitle) coloured from `sha256(name)`, written
  as `p_<slug>.png`, `g_<slug>.png`, `c_<slug>.png`, `b_<id>.png`. Distinct
  filenames matter — identically named `ContentFile`s collapse in storage.
- **Money flows through the real services.** Seeded orders call
  `mark_cod_collected` on delivery, so order and payment states can never
  disagree. Writing those fields directly produced "Unpaid" orders with
  `verified` payments.
- **`--flush` is a true reset** — tickets → refunds → payments → orders →
  promotions → banners → slabs → products (hard delete) → categories (two-pass).
  Foreign-key ordering and hard deletes are the whole trick here.

```bash
python manage.py seed_data            # create or repair
python manage.py seed_data --flush    # hard reset, then recreate
```

## Testing

Four layers, each proving something the others cannot.

### 1. Django test suite — 368 tests

```bash
cd backend
python manage.py test                # or: --parallel 4
python manage.py test apps.orders    # one module
python manage.py test apps.payments -v 2
```

Models and relationships, CRUD, serializer validation, HTTP status and error
codes, duplicates, stock validation, checkout, overselling, order lifecycle,
cash recording, refunds and transaction rollback.

47 of these cover authentication: both login workflows end to end, MFA
enforcement, OTP expiry/reuse/attempt limits/cooldown, hashed storage, session
creation and destruction, concurrent devices, role separation, password reset
and session revocation, and profile updates.

```bash
python manage.py test apps.authentication     # auth only
```

Includes regression tests for the two concurrency bugs found by probing:

- `CartServiceTests.test_cart_creation_survives_a_lost_race`
- `WishlistServiceTests.test_default_wishlist_recovers_from_lost_race`

Both **fail against the original implementations** and pass against the fix —
they were A/B verified rather than assumed correct.

### 2. Live smoke suite — 117 checks

Hits a running API over real HTTP across 12 sections. Creates run-scoped
fixtures and removes them at teardown, so it is safe to run on repeat.

```bash
cd /path/to/ums_mart
python run_smoke.py        # exits 0 on success, 1 on any failure
```

Expected: `SMOKE RESULT: 117 passed, 0 failed`. Afterwards the catalogue and
customer counts are unchanged.

The authentication API has its own live check, which asserts the full admin and
customer flows over HTTP and inspects the resulting rows in PostgreSQL:

```bash
cd backend
python scripts/e2e_auth_check.py     # exits 0 only when every check passes
```

Expected: `48 passed, 0 failed`. It clears rows in the `auth_*` tables between
phases; commerce data is never touched.

### 2b. Login UI suite — 30 checks

Drives both login interfaces in Chromium: the redirect when signed out, both
steps of each flow, the session surviving a reload, the account menu, and
sign-out. Fails on any JS error.

```bash
cd frontend
python ui_auth_e2e.py
```

Expected: `30 passed, 0 failed`.

### 3. Front-end contract suite — 165 checks

```bash
cd frontend
python frontend_e2e.py
```

Talks to the API exactly as the React apps do: carts, coupons, addresses,
checkout, the full order lifecycle, cash recording, refunds,
refunds, promotions, banners and store settings. Each run
creates its own `E2E Buyer` shopper (first-order coupons then apply) and
purges it afterwards.

### 4. UI smoke + screenshots — 30 shots

```bash
cd frontend
python ui_smoke.py both        # or: customer | admin
```

Drives both apps with Playwright/Chromium, **signs in through the real login
screens first**, walks every page, asserts that each route renders real data
rather than a skeleton, then writes full-page screenshots to
`frontend/screenshots/`. The run fails on **any** console error,
page error or failed request — a green run is "NO CONSOLE ERRORS, NO PAGE
ERRORS, NO FAILED REQUESTS".

| Range | App |
|---|---|
| `01`–`16` | customer storefront (incl. mobile home) |
| `20`–`34` | admin console (incl. form validation, settings tabs, 390 px mobile) |

## Project layout

```
ums_mart/
├── backend/
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py             shared configuration
│   │   │   ├── development.py      DEBUG, console email, permissive CORS
│   │   │   └── production.py       HTTPS, HSTS, secure cookies, fail-closed secrets
│   │   ├── urls.py                 /api/v1/, schema, docs, health
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── common/                     shared models, errors, pagination, identity
│   ├── apps/
│   │   └── <module>/
│   │       ├── models.py           schema, constraints, indexes
│   │       ├── selectors.py        read queries
│   │       ├── services.py         business logic, transactions
│   │       ├── serializers.py      validation + representation
│   │       ├── views.py            thin HTTP layer
│   │       ├── filters.py          query-parameter filters
│   │       ├── urls.py             routes
│   │       ├── admin.py            Django admin
│   │       ├── apps.py             AppConfig
│   │       ├── migrations/
│   │       └── tests/
│   ├── media/                      user uploads (git-ignored)
│   ├── static/                     source assets
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── customer-web/               React storefront (Vite, :5173)
│   │   ├── src/pages/              15 routes
│   │   ├── src/components/         shared UI, layout, product cards
│   │   ├── src/services/           one module per backend module
│   │   └── src/contexts/           Cart, Wishlist, Toast, Customer
│   ├── admin-dashboard/            React admin console (Vite, :5174)
│   │   ├── src/pages/              13 routes
│   │   └── src/components/forms/   modal create/edit forms
│   ├── frontend_e2e.py             front-end contract suite (145 checks)
│   ├── ui_smoke.py                 Playwright walk + screenshots
│   └── screenshots/                31 full-page PNGs
├── deployment/                     Nginx, Gunicorn, systemd, deploy + backup
├── docs/                           architecture, API, auth, testing guides
├── run_smoke.py                    live smoke suite runner
├── .env.example
├── .gitignore
└── README.md                       ← you are here
```

---

## Configuration

All configuration comes from environment variables — **no secrets or database
credentials are hardcoded anywhere.** `.env.example` documents every variable.
Three settings modules:

| Module | Use |
|---|---|
| `base.py` | shared by both |
| `development.py` | `DEBUG=True`, console email, permissive CORS, SQL echo option |
| `production.py` | `DEBUG=False`, HTTPS redirect, HSTS, secure cookies, required secret, mandatory `ALLOWED_HOSTS` |

`production.py` refuses to start without a strong `DJANGO_SECRET_KEY` and an
explicit `DJANGO_ALLOWED_HOSTS`, so a misconfigured server fails loudly instead
of leaking tracebacks.

---

## Deployment

See **[`deployment/README.md`](deployment/README.md)** for the complete
Hostinger VPS walkthrough: PostgreSQL hardening, Gunicorn/systemd, Nginx with
TLS, firewalls, SSH hardening, backups, restore drills and troubleshooting.

```bash
# Deploy or update
sudo -u umsmart bash /home/ums_mart/deployment/scripts/deploy.sh

# Back up
sudo -u umsmart bash /home/ums_mart/deployment/scripts/backup.sh
```

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | layering, module boundaries, transaction and locking strategy |
| [`docs/API.md`](docs/API.md) | endpoint reference, conventions, error catalogue, worked examples |
| [`backend/docs/authentication_api.md`](backend/docs/authentication_api.md) | the authentication module: every endpoint, request/response bodies, OTP policy, Postman walkthrough |
| [`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md) | historical note on the original `X-Customer-Id` identity seam |
| [`docs/TESTING.md`](docs/TESTING.md) | what is covered, how to run it, and the exact results (all four layers) |
| [`deployment/README.md`](deployment/README.md) | VPS setup and operations |

---

## License

Proprietary — © UMS Mart. All rights reserved.
>>>>>>> f13b331 (Initial commit)
