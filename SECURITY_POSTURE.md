# Security posture — current build

**Status: not safe to expose beyond this sandbox.** The note "no authentication is
enabled" is *almost* right, and the difference matters: authentication exists and
works, but **authorization is not enforced on the customer/commerce API**. Any
process that can reach port 8000 can read and write every customer's data.

Audited 2026-11-12 by probing the running server anonymously.

---

## What actually works (don't rip these out)

| Area | State |
|---|---|
| Customer OTP login (`/api/customer/*`) | Real: backend-generated codes, expiry, cooldown, attempt limits |
| Admin login + MFA (`/api/admin/*`) | Real: password + second factor, session rows |
| JWT + server-side session validation | Real: tokens carry `session_id`; logout and password change revoke |
| Storefront pages (`/profile`, `/orders`, `/cart`) | Gated client-side, and the *customer-scoped* cart/wishlist/checkout paths do check the token |
| Admin dashboard writes | Mostly protected — `PATCH /store-settings/`, order status changes and admin login all refuse anonymous callers (401/403/404) |

So this is not a dead-auth build. It is a build where the **generic CRUD viewsets
were never given permission classes**.

---

## What is open right now (verified, not theoretical)

Root cause: `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES` is `AllowAny` (a deliberate
"catalogue browsing stays open" choice), and the customer-scoped viewsets rely on
an `X-Customer-Id` / `?customer=` seam instead of requiring a token. So:

| Probe | Result |
|---|---|
| `GET /api/v1/customers/` | **200** — all 4 customers: names, mobiles, emails |
| `GET /api/v1/customers/1/` | **200** — one customer's full record |
| `GET /api/v1/addresses/?customer=1` | **200** — recipient name, mobile, house number, street, landmark, PIN |
| `GET /api/v1/orders/` | **200** — every order with customer name and mobile |
| `GET /api/v1/payments/` | **200** |
| `POST /api/v1/customers/` | **201** — creates a customer |
| `PATCH /api/v1/customers/2/` | **200** — **renamed a real customer** |
| `POST /api/v1/addresses/` | **201** — adds an address to any customer |
| `DELETE /api/v1/addresses/1/` | **204** — **hard-deleted a real address** |

### Damage this audit caused (repaired)

I ran those two writes to prove the hole was real rather than assume it. They did
land:

- customer 2 was renamed `HACKED` → **restored to `Diya Patel`**
- address 1 was hard-deleted → **recreated** (same recipient/address/city/PIN, default flag)
- a test customer `+919999888877` was created → **removed**

Verified afterwards: 4 customers with correct names, address counts back to
2 / 16 / 2 / 2. Address ids are not contiguous any more (the deleted row's id is
retired); nothing references it.

---

## Also true, and easy to forget

- **The API is bound to `0.0.0.0:8000`**, not `127.0.0.1`. It is reachable from
  anything that can route to this sandbox — not just localhost.
- **Development settings are live**: `DEBUG = True`, and `AUTH_DEV_MODE = True`,
  which means `POST /api/customer/send-otp/` **returns the OTP in the response**
  (`dev_otp`). Anyone who can reach the port can log in as any mobile number
  without receiving the SMS.
- Writes on the catalogue/admin side are refused, but reads of personal data are not.

---

## What I have not changed

I stopped short of adding permission classes to the customer/order/address/payment
viewsets. Reason: it is not a one-line change, and doing it carelessly breaks the
storefront.

- The storefront's **guest** paths depend on the same viewsets resolving identity
  from the guest cart key rather than a token. Blanket `IsAuthenticated` would
  break guest browsing and guest checkout — the round-26 business rule.
- The admin dashboard reads the same endpoints with an admin token; scoping by
  customer must keep admins seeing everything.
- Round 26 already fixed the worst instance of this pattern (`/api/v1/orders/`
  now scopes a *signed-in customer* to their own orders), which is why the fix
  needs to be per-viewset with a clear rule, not a global switch.

**Proposed rule if you want it closed:**
1. Reads of a specific customer's record, addresses, orders and payments require
   either that customer's own token or an admin token — no `X-Customer-Id` fallback.
2. Keep `AllowAny` for catalogue, categories, banners, store settings and the
   guest-cart/checkout-preview paths.
3. Delete the `X-Customer-Id` seam entirely once the storefront no longer needs it.
4. Run the storefront against `production.py` settings (`DEBUG=False`,
   `AUTH_DEV_MODE` inert) for anything that is not this sandbox.

Say the word and I will implement 1–3 with tests; it touches roughly six viewsets
and every one of them has an existing suite to prove it still works.
