# Round 26 — Industry-level customer authentication

**Guest shopping stays open. A mobile number and an OTP are asked for at checkout, and nowhere else.**

---

## 1. What a shopper experiences now

| Step | Guest | Signed-in customer |
|---|---|---|
| Browse, categories, search, filters, sort | ✅ open | ✅ open |
| Product details, stock, delivery estimate | ✅ open | ✅ open |
| Add / increase / decrease / remove, view cart | ✅ open, persisted in PostgreSQL against a guest key | ✅ open, persisted against the account |
| Header, top right | **Login** button | **My account** — name, then My profile / My orders / Saved addresses / Logout |
| Cart icon | live count | live count |
| `/checkout` | redirected to `/login` with *"Login to continue with your order"* and a promise the cart is safe | straight to checkout |
| `/orders`, `/profile`, `/addresses`, `/wishlist` | redirected to login | open |
| `/track` (order number + mobile lookup) | ✅ still open, no account needed | ✅ |

The basket is never cleared — not when you click Checkout, not while you type the OTP, not when you land back on checkout. It survives a refresh mid-flow and a full page reload.

---

## 2. The two customer paths

**Existing customer** — recognised from PostgreSQL by their verified mobile. Profile, name, contact and saved addresses load, and the guest basket merges into their account cart: quantities add, nothing duplicates, stock and prices are re-read from the database. They land **directly on checkout** with their addresses listed and preselected. Nothing to re-type.

**New customer** — the account is created the moment the OTP verifies. The mobile is stored as verified; there is no password and no second OTP in the same session. Checkout asks for the full name and address (house/flat, street/area, landmark, city, state, PIN) and the mobile arrives already filled in. The address is saved for next time, and the name is written back to the profile so the next sign-in greets them properly. The same mobile always resolves to the same account — never a duplicate.

---

## 3. Session handling

- A **short-lived access token** (in browser storage, used per request) and a **refresh token in an HttpOnly cookie**. JavaScript cannot read that cookie; `document.cookie` does not contain it. Verified in the browser during testing.
- The cookie is `HttpOnly`, `SameSite=Lax`, scoped to `/api/auth/`, and flips to `Secure` via `SESSION_COOKIE_SECURE` in production.
- Refresh is validated server-side and **rotates**: the old token is blacklisted the moment a new pair is issued. Logout and "log out everywhere" clear the cookie.
- A reload restores the session silently — the app trades the cookie for a fresh pair before asking who the customer is, so an expired access token never surfaces as "your session ended".
- Multiple tabs and multiple devices work simultaneously.
- Only a request that actually carried a token can end a session. A guest hitting an account-only endpoint no longer wipes anything.

---

## 4. OTP security

Generated and verified only on Django; React contains no OTP logic and no secrets. Indian mobile validation and international formatting, 5-minute expiry, 60-second resend cooldown, per-mobile and per-IP request plus attempt limits, single-use codes, specific error messages. In production no code value appears in the response or the logs; in development the response carries only `dev_otp` behind a mock-mode flag, so the dev server says plainly that SMS is not configured.

---

## 5. Files

### Changed — backend
| File | Change |
|---|---|
| `backend/apps/authentication/services/auth_service.py` | `_merge_guest_cart()` folds the guest basket into the account **inside verify-otp**; response gains `cart_merged` |
| `backend/apps/authentication/views.py` | `REFRESH_COOKIE` + `_set_refresh_cookie` / `_clear_refresh_cookie`; verify-otp and refresh set/rotate it, logout and logout-all clear it; refresh accepts cookie or body |

### Changed — storefront
| File | Change |
|---|---|
| `src/App.jsx` | Rewritten: Auth/Customer/Wishlist providers restored, login + gated account routes, public `/track` restored |
| `src/components/common/RequireAuth.jsx` | Carries the intended destination and a checkout reason; placeholder while the session is confirmed |
| `src/components/layout/NavBar.jsx` | Login ⇄ My account with name, mobile, profile/orders/addresses/logout; wishlist icon for signed-in customers only |
| `src/components/layout/FootBar.jsx` | "Track an order" points at the public lookup |
| `src/pages/Login/LoginPage.jsx` | "Login to continue with your order" banner, item count reassurance, returns to the exact destination |
| `src/pages/Cart/CartPage.jsx` | Checkout hands off to login with the basket size; button caption adapts to the session |
| `src/pages/Checkout/CheckoutPage.jsx` | Rewritten for the authenticated flow: saved addresses with select/add, new-customer address form, verified mobile prefilled, name persisted after the first order |
| `src/context/AuthContext.jsx` | Guest key rides along on verify-otp; silent refresh before profile on restore |
| `src/context/CartContext.jsx` | Refreshes on session and customer change; retires the guest key once the basket is owned |
| `src/services/api.js` | Guest-first identity: bearer when signed in, guest key otherwise; `withCredentials`; sign-out only on a token-bearing failure |
| `src/services/authService.js` | Refresh token out of localStorage (memory + cookie); cookie-aware `hasSession`; `sessionExpired`; rotation-safe `withSession` |
| `src/services/orderService.js` | `checkoutOrder` for the authenticated endpoint; guest checkout kept for compatibility |
| `frontend/ui_auth_e2e.py` | Guest-first storefront assertions plus a new customer-journey suite (41 checks) |

### New files
None. Every screen the round needed already existed on disk from the earlier auth work and was reused.

### Endpoints
No new routes. The round wires existing ones together:
`POST /api/customer/send-otp/`, `POST /api/customer/resend-otp/`, `POST /api/customer/verify-otp/` (now reads `X-Guest-Cart`), `GET /api/customer/profile/`, `PATCH /api/customer/profile/`, `POST /api/customer/logout/`, `POST /api/auth/token/refresh/` (cookie-aware), `GET /api/auth/session/`, `POST /api/auth/logout-all/`, `GET /api/v1/cart/`, `POST /api/v1/cart/items/`, `GET /api/v1/addresses/mine/`, `POST /api/v1/addresses/mine/add/`, `POST /api/v1/orders/checkout/preview/`, `POST /api/v1/orders/checkout/`, `GET /api/v1/orders/lookup/`.

### Migrations
**None.** The round reuses `accounts_user`, `accounts_customer_profile`, `customers_customer`, `addresses_address`, `cart_cart`, `cart_item`, `auth_otp_verification`, `auth_otp_throttle`, `token_blacklist_*`, `orders_order`, `orders_order_item`, `payments_payment`. `makemigrations --check` reports no changes.

### Config
No new environment variables. `SESSION_COOKIE_SECURE` now also governs the refresh cookie.

---

## 6. Verification

| Suite | Result |
|---|---|
| `manage.py test` (whole backend) | **374/374 OK** |
| `scripts/e2e_auth_check.py` | 48/48 |
| `frontend/frontend_e2e.py` | 165/165 |
| `frontend/ui_auth_e2e.py` (incl. new journey) | **41/41** |
| `frontend/ui_smoke.py` | clean — 27 screenshots, no console/page errors, no failed requests |
| `run_smoke.py` | 121/121 |

**Scenarios driven through the real browser:**
- **A — new customer.** Browse → add 2 items → Checkout → login gate → OTP → auto-created account → land back on checkout with both items → fill address → place order → confirmation `UMS-20261112-XYW4L6`.
- **B — existing customer.** Guest adds an item → gate → OTP → merged into the account with no duplicate → saved address preselected on checkout.
- **C — voluntary login.** Login from the header lands home with the cart intact and the header showing the account.
- **D — returning session.** Reload keeps the session; checkout opens without re-authentication; a second tab shares it; a deliberately corrupted access token is silently replaced by rotation.

**Also checked:** mobile 390 px (0 px horizontal overflow on home, login gate and checkout), invalid OTP rejected, duplicate mobile resolves to one account, logout clears the cookie and re-gates `/profile`, multi-tab, and that `ums_refresh` is absent from `localStorage` and unreadable from `document.cookie`.

---

## 7. Database state

Restored to baseline after testing: **4 demo customers, 17 orders, 32 products, 1 admin**, 3 live carts, no OTP rows, no orphaned users.

---

## 8. Follow-up: "session is killing after login in a fraction of seconds"

Reported after the round shipped. Three separate defects combined into that one
symptom. All three are fixed and covered by tests.

### Why it happened

**1. An expired access token 401'd the entire public storefront.**
DRF's `JWTAuthentication` rejects a request as soon as the presented token fails
verification — before permissions are consulted. So a browser holding an expired
token got 401 from the catalogue, store settings and banners; the storefront read
a 401 on its own data as "the session is dead" and signed the shopper out. One
stale token was indistinguishable from a revoked session.

> Fix — `apps/authentication/authentication.py`: `SessionAwareJWTAuthentication.authenticate()`
> now treats an unverifiable token as *no identity* rather than a hard failure.
> A token that cannot be verified proves nothing, so "anonymous" is the honest
> answer and each endpoint's own permission class decides. Account endpoints
> still return 401 via the normal `NotAuthenticated` path.

**2. `customer_context_required` was treated as proof of expiry.**
When a stale token reached `/api/v1/cart/`, the server answered
`customer_context_required` — "we could not tell whose cart this is". The client
mapped that code straight to `clearSession()`. But that answer is produced by any
unresolvable identity, including a token that merely needs renewing.

> Fix — `services/api.js`: on that code the client now attempts a refresh and
> replays the request first, and only clears the session if the server *refuses*
> to renew. The guest basket key is also sent alongside the bearer as a fallback
> identity, so such a request degrades to the guest cart instead of becoming
> fatal.

**3. Any transient failure ended the session, and rotation raced across tabs.**
`refreshSession()` called `clearSession()` on *every* error — a 503, a timeout, a
dropped connection. Separately, rotation is single-use, so two tabs refreshing at
the same instant meant the loser was handed a blacklisted token, answered 401 and
signed itself out.

> Fix — `services/authService.js` gains `isSessionDead()`: only 401/403 and an
> explicit `token_not_valid` end a session; everything else is transient and
> leaves the tokens untouched. `refreshSession`, the retry interceptor and
> `AuthContext.revalidate` all use it.
>
> Fix — `apps/authentication/services/session_service.py`: a **30-second rotation
> grace window**. When the presented token was blacklisted moments ago by a
> rotation on the same live session, the caller is a concurrent tab, not a thief,
> so it gets a fresh pair. Replay outside the window, expired tokens and dead
> sessions are still refused — verified by test.

### Also fixed while in there
`GET /api/v1/orders/` was unscoped: any caller, even one with no token, could
list **every customer's orders**. A signed-in customer now sees only their own;
admins and the guest lookup path are unchanged.

### Verified
| Check | Result |
|---|---|
| Backend suite | **375/375 OK** |
| `ui_auth_e2e.py` | 41/41 |
| `frontend_e2e.py` | 165/165 |
| `run_smoke.py` | 121/121 |
| Access token expired → reload | stays signed in, token silently renewed |
| Two tabs refreshing simultaneously | both stay signed in |
| One refresh call returns 503 | session preserved, not signed out |
| Replay outside the grace window | still 401 |
| Customer listing orders | sees only their own (8 of 17) |

---

## 9. Preview restart (housekeeping)

The `:5173` listener was an orphan from an earlier tool session — it answered on
localhost but was no longer registered as the live preview or manageable. Stopped
that tree and restarted it under the process manager.

While smoke-testing the restart, `/api/v1/wishlist/` returned **404** to a stale
token. Cause: the view had no `permission_classes`, so an unverifiable token fell
through to the identity seam, which tried to resolve a customer and reported
`not_found` — indistinguishable from "this route does not exist".

> Fix — `apps/wishlist/views.py`: `MyWishlistView` and `WishlistToggleView` now
> declare `IsAuthenticated`. An expired token gets a clean **401** (which the
> client already knows to renew) instead of a misleading 404.
> Two tests in `test_addresses_wishlist_banners.py` were updated to sign in
> through the real OTP flow rather than the legacy `X-Customer-Id` seam.

**State:** storefront `:5173` running (pid 736913), admin `:5174`, API `:8000`.
Browser pass: 56 product cards, guest cart, checkout gate, OTP login, and
`/orders` `/wishlist` `/profile` all load with **zero 4xx and zero JS errors**.
Backend **375/375** green. DB at baseline: 4 customers, 17 orders, 32 products,
1 admin + 4 demo logins.

## 10. Round 29 — JWT kept, session management removed

**The ask:** *"keep JWT token, remove session management and create it off."*

The round-26 design stored a `UserSession` row per login and checked it on every
request. That row was the thing dying mid-browse in round 27, and it was never
load-bearing: Simple JWT already signs the user, the role, and the expiry into the
token. So the row is gone and the token is now the whole story.

### What changed

| Before | After |
|---|---|
| `auth_user_session` row per login | **table dropped** (`0002_delete_usersession`) |
| Every request looks the row up | no lookup, no per-request query |
| `session_id` in the login payload | **removed** — deliberate API change |
| Logout deactivates the row | logout **blacklists the refresh token** |
| 8-hour absolute session lifetime | refresh token lifetime, nothing else |

`start_session()` still returns a 2-tuple so callers did not change; its first
element is now always `None`.

### The one row that stayed

Simple JWT only writes an `OutstandingToken` when `blacklist()` is called — that
is, when a token is *already* being revoked. Which means "log out everywhere" had
nothing to enumerate: a session that was never individually revoked was invisible.
Logout therefore succeeded with `sessions_revoked: 0` while the refresh token
stayed live.

> `start_session()` now records the refresh token's `jti` at **issue** time.
> That is the single piece of server state this stateless design keeps, and it is
> what makes a global sign-out actually global.

### Revocation rules

- **Logout** (`/api/customer/logout/`) blacklists the credential the caller
  presents — body token, else cookie. With neither, it blacklists **every**
  refresh token for the account, so it can never be a no-op. Access tokens already
  in memory stay valid until they expire — the accepted cost of stateless JWT.
- **Sign out everywhere** is `/api/auth/logout-all/`, and it is the only thing
  that ends *other* devices. Plain logout must not: a shopper leaving the site on
  a laptop should not be thrown off their phone.
- **Password reset / change** blacklists every refresh token; access tokens live
  out their remaining lifetime.
- **Rotation is single-use.** A second tab replaying the same refresh token within
  `ROTATION_GRACE_SECONDS = 30` receives **the identical pair** back (idempotent
  replay via cache key `jwt:rotated:{jti}`). A miss fails closed.

Four bugs surfaced while building this and all four were real:

1. The refresh cookie was scoped to `/api/auth/`, so the browser never sent it to
   `/api/customer/logout/` — logout silently could not blacklist anything.
   Widened to `/api/`, cleared on both paths.
2. The first grace-window implementation forgave *any* recent blacklist entry, so
   a deliberately logged-out token could be exchanged for another 30 seconds.
   Logout was effectively undoable. Replaced with the replay table above, which
   only ever remembers pairs minted by *rotation*.
3. **"Sign out everywhere" left a live token behind.** Rotation caches the pair it
   produced, and `refresh` consults that cache *before* the blacklist. So: rotate,
   then sign out everywhere, and the token that rotation minted kept working for
   the rest of the window — a global sign-out that signed nothing out. Revocation
   now clears the window, and clearing an entry also kills the pair it holds.
   `test_16b` covers it; it fails if the sweep is removed.
4. **Logout over-reached with a stale cookie.** If the browser still held an
   *expired* refresh cookie, no token could be revoked, so the view fell through
   to the "blacklist everything" fallback — signing the shopper out of their phone
   because they logged out on a laptop. A credential that was presented but is
   already dead now ends the request: nothing to revoke, nothing else touched.

### Verification

| Suite | Result |
|---|---|
| `manage.py test` | **375 passed** |
| `apps.authentication` | 45 passed |
| `scripts/e2e_auth_check.py` (real HTTP) | **49 passed, 0 failed** |
| `frontend/ui_auth_e2e.py` (browser) | **41 passed, 0 failed** |
| `frontend/frontend_e2e.py` | **166/166 checks** |
| `run_smoke.py` | **123 passed, 0 failed** |

Browser pass: guest add → checkout gate → OTP login → cart preserved → reload
still signed in → expired access token renewed without a sign-out → `/orders`,
`/profile`, `/cart` all load → logout returns the header to `Login` → `/profile`
redirects to `/login` → re-login works. **Zero JS errors.**

Two suites had been authenticating the wishlist with the legacy `X-Customer-Id`
seam, which round 28 closed (401). Both now sign in through the real OTP flow and
carry a bearer token, which is what a browser does.

### Known limits

- `LocMemCache` is per-process, so rotation replay assumes one worker. A real
  deployment needs Redis; the code fails closed if the cache is unavailable.
- `DEBUG=True` and `AUTH_DEV_MODE=True` mean `/api/customer/send-otp/` returns
  `dev_otp`. Fine for a local demo, must be off anywhere reachable.
- Authorization is still not enforced on the customer/order/address/payment
  viewsets — see `SECURITY_POSTURE.md`. That is the open security item, and it is
  separate from this work.

## 11. Round 30 — JWT removed, Django sessions

**The ask:** *"Replace JWT/token authentication with Django session-based
authentication."* And, before implementing: *identify the reason sessions are
being destroyed or users are logged out automatically, and fix the root cause.*

### The root cause

Rounds 26–29 kept fixing the *symptoms*. The actual cause was a design decision
that made them inevitable: **the client held credentials with their own expiry,
so two systems had to keep agreeing about whether a user was signed in — and
they kept disagreeing.**

Concretely, a signed-in shopper could be thrown out by any of:

| Trigger | What happened |
|---|---|
| access token past `exp` | read as "session over" before the server was asked |
| a single failed refresh | rotation error treated as a dead session |
| a rotation replay that missed its 30 s window | 401 on a perfectly good token |
| `customer_context_required` on a cart call | indistinguishable from "expired" |
| any per-request `UserSession` lookup | a second opinion that could say no |

Each round patched one path. The remaining paths kept firing. A session row has
none of this: there is no expiring access credential, no refresh step, and no
client-side flag that can be wrong. **One source of truth.**

The class of bug is now structurally impossible, not merely patched: a request
carries a cookie, the server looks up a row, and the answer is yes or no.

### What changed

| Removed | Added |
|---|---|
| `djangorestframework-simplejwt` (uninstalled) | `django.contrib.sessions` (DB-backed) |
| `SIMPLE_JWT`, `JWT_*` settings | `SESSION_COOKIE_AGE = 7 days` |
| `token/refresh/` endpoint | `GET /api/auth/csrf/` |
| `OutstandingToken` / `BlacklistedToken` tables (dropped) | `UmsSessionAuthentication` |
| rotation grace cache + replay | `apps/authentication/backends.py` (`OTPBackend`) |
| `access` / `refresh` in login payloads | `login()` / `logout()` |

`SessionAwareJWTAuthentication` → `UmsSessionAuthentication`. The old class name
is gone, not aliased: nothing should be able to import JWT by habit.

### The requirement checklist

| # | Requirement | Where |
|---|---|---|
| 1 | DB-backed sessions | `SESSION_ENGINE = ...backends.db` |
| 2 | customer OTP → `login()` | `session_service.start_session` |
| 3 | admin password + email OTP → session | `admin_verify_mfa` |
| 4 | session id only in HttpOnly cookie | `SESSION_COOKIE_HTTPONLY = True`; both apps purge legacy token keys on boot |
| 5 | `withCredentials: true` | both `services/api.js` |
| 6 | CORS + CSRF | `CORS_ALLOW_CREDENTIALS`, `CSRF_TRUSTED_ORIGINS`, `/api/auth/csrf/` |
| 7 | session verification API | `GET /api/auth/session/` |
| 8 | reload restores without OTP | `AuthProvider` boot effect |
| 9 | seven-day expiry | `SESSION_COOKIE_AGE = 604800` |
| 10 | `SESSION_EXPIRE_AT_BROWSER_CLOSE = False` | base + production |
| 11 | never log out on navigation/refresh | only a 401 ends a session |
| 12 | explicit `logout()` | `LogoutView` |
| 13 | role-based authorization | `IsAdminRole` / `IsCustomerRole` + session role pin |
| 14 | redirect only on confirmed 401 | `isSessionDead()` = `status === 401` |
| 15 | JWT machinery removed | package uninstalled, tables dropped |

### Three real bugs found while doing this

**1. Unauthenticated requests returned 403, not 401.**
DRF picks 401 vs 403 by asking the authenticator for a `WWW-Authenticate`
challenge, and `SessionAuthentication` returns `None` — so "no session" arrived
as 403. That distinction is load-bearing: the storefront keys its redirect
strictly on 401, so a missing session would have looked like "signed in but not
allowed" and the shopper would sit on a page of permission errors. Fixed by
returning a `Session realm="ums-mart"` challenge.

**2. CSRF would have blocked every write, silently.**
A SPA never receives a `{% csrf_token %}` template tag, so it has no token and
Django refuses every POST — which reads as "the login button does nothing". Added
`GET /api/auth/csrf/` and `ensureCsrf()` on both frontends. Note `login()`
rotates the token with the session key, so clients must re-read the cookie after
signing in; the interceptors read it per request, so they do.

**3. A latent identity bug in the smoke test.**
`RUN_NUM` was 7 digits prefixed with `+919`, producing an 11-character number.
The commerce API stores what it is sent; the OTP layer canonicalises. So the
smoke Customer row (`+9192272492`) and the account created by signing in with
that number (`+919192272492`) were **different identities** — and checkout looked
up an address owned by nobody the run was signed in as. Under JWT this was
masked because the bearer took precedence over the header. With sessions the
mismatch surfaced as a 404. `RUN_NUM` is now a valid 9-digit suffix.

### Verification

| Suite | Before | After |
|---|---|---|
| `manage.py test` | 375 | **377** |
| `scripts/e2e_auth_check.py` | 49 | **54** |
| `frontend/ui_auth_e2e.py` | 41 | **47** |
| `frontend/frontend_e2e.py` | 166 | **166** |
| `run_smoke.py` | 123 | **124** |

The browser suite now asserts the things this round is actually about:
session cookie lives seven days, is HttpOnly, is unreadable from JavaScript, and
**navigation across `/cart` `/orders` `/profile` `/` never re-authenticates.**

Live HTTP checks (16/16): anonymous → 401; OTP login sets the cookie and returns
no token; five consecutive profile calls stay 200; a fresh cookie jar is signed
in; logout without `X-CSRFToken` is refused **and does not kill the session**;
logout with it ends the session and the old cookie value is dead.
Admin 11/11: password → challenge → MFA → session; admin blocked from customer
endpoints; session survives reload. Cart 8/8: guest basket merged at sign-in and
survives the reload. Role demotion returns a clean 401.

### Known limits

- `clearsessions` must run on a schedule, or expired rows accumulate.
- `AUTH_DEV_MODE=True` still returns `dev_otp`. Off anywhere reachable.
- Authorization is still not enforced on the customer/order/address/payment
  viewsets — `SECURITY_POSTURE.md`. Sessions fix *who you are*; that gap is about
  *what you may touch*, and it remains open.

## 12. Round 32 — the cart that emptied on sign-in

> Reported as: *"I added 2 items to cart, then logged in successfully, but what I
> added was not stored after login."*

### The root cause

Not a frontend ordering bug, and not a missing merge. The merge was running
**too early, and against a session the browser did not have**.

`customer_verify_otp()` did two things in one request:

1. `session_service.start_session()` — put the session id in an HttpOnly cookie.
2. `_merge_guest_cart()` — move the anonymous basket into that account.

Step 2 assumed step 1 had worked. It had not. The preview renders the storefront
inside a frame whose top-level origin is different, so the storefront is a
**third-party context**, and a `SameSite=Lax` cookie is neither stored nor sent
there. The browser accepted the `Set-Cookie` header and discarded it.

The damage followed directly:

| Step | What happened |
|---|---|
| verify-otp | 200, `Set-Cookie` ignored, DB session row created |
| merge (same request) | 2 guest lines moved into that account |
| guest cart | `status='merged'`, 0 lines — the basket was gone |
| `GET /api/auth/session/` | 401 — the cookie never came back |
| every later cart call | anonymous, with a *fresh* guest key → empty cart |

So the items were not "not stored". They had been stored — in an account the
browser could never open again, which is worse. `DELETE FROM django_session`
shows the row was there the whole time.

Confirmed by printing the response and the cookie jar side by side:

```
POST /customer/verify-otp/  200  set-cookie: <none>
GET  /auth/session/         401
jar: []
localStorage ums.guestCartKey: minted fresh on next read
```

### What changed

**Backend — the merge is deferred until a session is proven live.**

- `verify-otp` no longer moves the basket. It reports `cart_merge_pending: true`
  if a guest basket is waiting (`auth_service._guest_key_from`,
  `cart.services.guest_cart_has_items`).
- `apps.cart.views._cart_for()` calls `services.adopt_guest_cart()` on any
  request that resolves to a **signed-in customer**. That request exists only
  because a cookie round-tripped, so the merge can only land in a cart the
  shopper can actually open.
- `adopt_guest_cart()` is idempotent (a merged basket has no live guest cart
  left, so the next call is a no-op) and never raises into the request.
- The old eager `_merge_guest_cart()` is deleted so the unsafe path cannot come
  back.

**Frontend — never claim a sign-in that the browser did not keep.**

- `AuthContext.verifyOtp()` now re-reads `GET /api/auth/session/` after the OTP
  is accepted and only then sets the user. If the session is not there, it
  throws `session_cookie_blocked` and leaves local state untouched.
- `CartContext` retires the guest key **after** awaiting the post-login refresh,
  not in a parallel effect. The parallel version raced the fetch and handed the
  server a brand-new key, which is how the merge silently matched nothing.
- `guestCart.getGuestKey()` keeps an in-memory copy, so a `localStorage` that
  refuses writes no longer mints a different key on every call.
- `LoginPage` shows a plain explanation ("this browser blocked the sign-in
  cookie — your cart is still saved") instead of a code that "did not work".

**Settings — the cookie is now correct for both environments.**

`config/settings/development.py` gains `COOKIE_CROSS_SITE` (default **off**):

| | `COOKIE_CROSS_SITE=0` (default) | `COOKIE_CROSS_SITE=1` |
|---|---|---|
| SameSite | `Lax` | `None` |
| Secure | `False` | `True` |
| Use | `http://localhost:5173` | `https://*.e2b.app` preview |

SameSite is a property of the cookie, so it cannot be both at once; the switch
is explicit rather than a guess. The localhost default is unchanged, which keeps
previous behaviour working.

`https://*.e2b.app` is also added to `CSRF_TRUSTED_ORIGINS` and to
`CORS_ALLOWED_ORIGIN_REGEXES` in development, so an unsafe request from the
preview host is not rejected as a CSRF failure.

### The second bug fixed on the way

A first-time visitor who pressed checkout was sent to `/login` and greeted with
**"Your session ended. Please sign in again to continue."** They had never signed
in. The gate's 401 was setting `sessionLost` unconditionally. It is now set only
when `getStoredUser()` proves this browser had a session to lose.

### Ordering, after the fix

```
POST /customer/verify-otp/            200   session row created, cookie set
GET  /auth/session/                   200   cookie proven  ← user flips here
GET  /api/v1/cart/                    200   adopt_guest_cart() runs, 2 lines moved
                                             → response already contains them
                                             → guest key retired after this
```

If the cookie is refused, the sequence stops at the second line, `isAuthenticated`
never flips, and the key and basket stay exactly where they were.

### Known limits

- `COOKIE_CROSS_SITE=1` requires HTTPS. Over plain HTTP the browser drops a
  `Secure` cookie and every request arrives anonymous — the exact failure this
  round fixed. Only set it behind TLS.
- The `ums_mart_sessionid` cookie is `SameSite=None` in that mode, so it is sent
  on cross-site requests generally. Acceptable for a preview host; do not carry
  the flag into a deployment under a shared domain without revisiting it.

## 13. Round 33 — two dependencies missing from requirements.txt

Reported as a crash on Windows during `manage.py runserver`:

```
File "backend\apps\notifications\services\email_service.py", line 21, in <module>
    import requests
ModuleNotFoundError: No module named 'requests'
```

The import chain is `urls_admin` -> `views` -> `auth_service` -> `email_service`,
so the failure surfaced as a URL-configuration error rather than a notification
one. The cause was simply that `requirements.txt` did not list everything the
code imports. Both modules were present in the development sandbox as transitive
dependencies of other packages, which is why a clean `pip install` reproduced a
crash that never appeared there.

| Missing | Used by | Consequence |
|---|---|---|
| `requests` | `email_service.py`, `sms_service.py` | API refuses to start at all |
| `argon2-cffi` | `Argon2PasswordHasher`, first in `PASSWORD_HASHERS` | 49 test errors; every admin login, password reset and `create_admin` fails |

Fixed by pinning both. `requests==2.33.0`, `argon2-cffi==25.1.0`.

### How it was verified this time

The earlier verification was invalid: it ran in an environment where these
packages happened to be installed globally, so a missing pin could not show up.
The check that matters is a throwaway venv built from `requirements.txt` alone:

```bash
python3 -m venv /tmp/cleanvenv
/tmp/cleanvenv/bin/pip install -r backend/requirements.txt
/tmp/cleanvenv/bin/python backend/manage.py check      # no issues
/tmp/cleanvenv/bin/python backend/manage.py test       # 377 tests, OK
```

Before the pins: `check` crashed, `test` reported 49 errors. After: clean check,
377/377. `runserver` in that same venv serves `/health/` 200 and
`POST /api/customer/send-otp/` 200 — the endpoint whose import chain failed.

**Lesson:** a dependency that is importable in the dev environment is not
evidence that it is declared. Verify installs against a fresh venv, not the
working one.

## 14. Round 34 — `permission denied for schema public` on migrate

Reported on Windows after a clean install:

```
psycopg.errors.InsufficientPrivilege: permission denied for schema public
LINE 1: CREATE TABLE "django_migrations" ...
django.db.migrations.exceptions.MigrationSchemaMissing:
  Unable to create the django_migrations table (permission denied for schema public)
```

Not a code fault. Since **PostgreSQL 15**, the `public` schema no longer grants
`CREATE` to every role. It is owned by the pseudo-role `pg_database_owner`, so
only the owner of the *database* may create objects in it.

The setup instructions created the role and the database in one breath:

```sql
CREATE ROLE ums_mart_user ...;
CREATE DATABASE ums_mart_db OWNER ums_mart_user;
```

That is correct **only** when the database does not already exist. If
`ums_mart_db` was already there (from an earlier attempt, another project, or a
pgAdmin right-click), the `CREATE DATABASE` line fails with `already exists`,
people skip past it, and the role never becomes the owner. The role can connect
and list the schema, but cannot write to it — exactly the observed error.

### Reproduced and fixed

A throwaway role with no ownership of its database:

```
pgtest_role -> CREATE TABLE probe(x int);
ERROR:  permission denied for schema public      <-- same error
```

Two independent fixes were then verified:

| Fix | Statement | Result |
|---|---|---|
| Ownership | `ALTER DATABASE pgtest_db OWNER TO pgtest_role;` | `CREATE TABLE` succeeds |
| Explicit grant | `GRANT ALL ON SCHEMA public TO pgtest_role;` | `CREATE TABLE` succeeds |

Ownership is the better one, because on PG15+ it also covers objects created
later. After applying it, `manage.py migrate` ran the full chain
(`payments`, `promotions`, `sessions`, `store_settings`, `wishlist`) with no
errors on PostgreSQL 17.

### Documentation fix

`RUN_LOCAL.md` section 3 now carries an idempotent block that works whether or
not the role and database already exist — a `DO $$ ... $$` guard for the role,
plus an unconditional `ALTER DATABASE ... OWNER TO`. The whole block was executed
verbatim against PostgreSQL 17 twice (fresh, then re-run) to confirm it is
genuinely idempotent, and the `CREATE TABLE _probe` smoke check was run as the
unprivileged role.

## 15. Round 35 — `seed_data` crashed: "Collect the cash before marking this order delivered"

Reported on Windows on the first `seed_data` run of a fresh database:

```
File "common/management/commands/seed_data.py", line 159, in _seed_orders
    update_order_status(order, status, changed_by="seed_data")
common.exceptions.BusinessRuleError: Collect the cash before marking this order delivered.
```

The service layer was right. `seed_data` was wrong.

### The bug

`update_order_status()` enforces the cash-first rule:

```python
if new_status == OrderStatus.DELIVERED and locked.payment_status not in {
    PaymentStatus.PAID, PaymentStatus.COD_COLLECTED,
}:
    raise BusinessRuleError("Collect the cash before marking this order delivered.")
```

The seeder looped over the whole lifecycle first and *then* recorded the cash:

```python
for status in steps:                       # ... -> OUT_FOR_DELIVERY -> DELIVERED  (boom)
    update_order_status(order, status, ...)

if payment and final_status == "delivered":
    mark_cod_collected(payment, ...)       # too late
```

So the 5th step of the very first delivered order raised, and because the command
is atomic, the run aborted part-way through seeding.

### The fix

The collection now happens *before* the final transition, inside the same loop:

```python
for status in steps:
    if status == OrderStatus.DELIVERED and payment and final_status == "delivered":
        mark_cod_collected(payment, collected_by="seed_data")
    update_order_status(order, status, changed_by="seed_data")
```

`mark_cod_collected()` sets the payment to `PAID` **and** the order to
`COD_COLLECTED`, which is precisely the precondition the transition requires. The
rule is satisfied rather than bypassed — no guard was weakened, and the admin
cash-first gate is untouched.

### Verification

Against a throwaway database and role, migrated from scratch:

| Check | Result |
|---|---|
| `seed_data` on an empty DB | completes — 16 orders, 16 payments, 32 products |
| Second `seed_data` run | no crash, counts unchanged (16/16/32) — still idempotent |
| Delivered orders | 12 × `delivered` / `cod_collected` / payment `paid` |
| Non-delivered orders | `cod_due` / `pending` — correct, cash not yet collected |
| `manage.py test` | 377 tests, OK |

A half-seeded database (what the crash left behind) is not a problem: `seed_data`
is idempotent, so re-running it after this fix tops up whatever is missing.
`seed_data --flush` rebuilds from scratch if the partial state is confusing.
