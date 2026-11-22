# Authentication

**Round 30: Django session authentication.**

The API no longer uses JWTs. Authentication is Django's own session framework:
a session id in an HttpOnly cookie, a row in `django_session`, and `login()` /
`logout()` to manage it. Nothing token-shaped is issued, stored, rotated or
refreshed, and JavaScript never sees a credential.

If you are looking for the old JWT design, it is gone: the package is
uninstalled, `SIMPLE_JWT` and `JWT_*` settings are removed, `token/refresh/` no
longer exists, and the `token_blacklist` tables are dropped. See
[`ROUND26_AUTH.md`](../ROUND26_AUTH.md) §11 for why.

---

## Why sessions, and what was actually wrong

Through rounds 26–29 the browser held an access token in localStorage and a
refresh token in an HttpOnly cookie. A signed-in shopper kept being thrown out,
and every round fixed one more cause of it:

| Round | Cause | Fix |
|---|---|---|
| 26 | a per-login `UserSession` row | re-checked, still killed sessions |
| 27 | an expired access token read too eagerly | refresh before profile |
| 28 | wishlist had no permission class, so a stale token 404'd | `IsAuthenticated` |
| 29 | rotation replay could undo a logout | idempotent replay |

All of those were consequences of one design decision: **the client held
credentials with their own expiry, and the server had to keep agreeing with
them**. Two sources of truth meant two ways to disagree.

A Django session has one source of truth. There is no access token to look
expired, no refresh call that can fail, and no local flag to fall out of sync.
Either the row is in the table or it is not, and only the server decides.

---

## How it works

### 1. Login

Customers verify an SMS code; admins verify a password and then an email code.
On success the server calls `login(request, user, backend=OTPBackend)`, which:

- creates the session row,
- cycles the session key (session-fixation defence),
- sets `ums_mart_sessionid` as **HttpOnly**, `SameSite=Lax`, `Path=/`, 7-day.

The JSON response carries only `{user, is_new_customer}`. There is no
`access`, no `refresh`, and no `session_id`.

### 2. Every request

`SessionMiddleware` turns the cookie into `request.session`, then
`AuthenticationMiddleware` turns that into `request.user`. DRF's
`UmsSessionAuthentication` adds a role check and is the only configured
authentication class.

The cookie is sent automatically. The frontend does not attach anything.

### 3. Page load / refresh

The app calls `GET /api/auth/session/` once on mount:

| Status | Meaning | Action |
|---|---|---|
| 200 | still signed in; body carries the user | render as signed in |
| 401 | server confirms no session | redirect to login |

A **refresh costs one request and never asks for another OTP.**

### 4. Logout

`POST /api/customer/logout/` → `logout(request)` → session row deleted, cookie
cleared. Other devices are untouched.

`POST /api/auth/logout-all/` deletes every session for the account.

### 5. Expiry

`SESSION_COOKIE_AGE = 604800` (7 days), `SESSION_EXPIRE_AT_BROWSER_CLOSE = False`.
A shopper who closes the laptop is still signed in tomorrow. An expired session
is simply absent: the next request is a clean 401.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/auth/csrf/` | plant the CSRF cookie before any unsafe request |
| GET | `/api/auth/session/` | **200** signed in / **401** not. The page-load check |
| GET | `/api/auth/session/status/` | same, but always 200 with `authenticated: bool` |
| POST | `/api/customer/send-otp/` | request an SMS code |
| POST | `/api/customer/verify-otp/` | verify → **creates the session** |
| POST | `/api/customer/resend-otp/` | resend (60 s cooldown) |
| POST | `/api/customer/logout/` | end this session |
| POST | `/api/auth/logout-all/` | end every session for this account |
| POST | `/api/admin/login/` | username + password → MFA challenge |
| POST | `/api/admin/verify-mfa/` | email code → **creates the admin session** |
| POST | `/api/admin/logout/` | end this admin session |

`/api/auth/session/` answering 401 is the contract. Use
`/api/auth/session/status/` only where an error would be awkward.

---

## CSRF

Django rejects unsafe requests (POST/PUT/PATCH/DELETE) that do not carry
`X-CSRFToken` matching the `ums_mart_csrftoken` cookie. Both frontends:

1. call `/api/auth/csrf/` on boot, which plants the cookie;
2. re-read the cookie on every request and echo it in the header.

The CSRF cookie is deliberately **not** HttpOnly, because double-submit requires
reading it. It is not a credential on its own: it is useless without the session
cookie, which is HttpOnly.

> `login()` rotates the CSRF token along with the session key. A client that
> caches the token across a login will send a stale one; re-read the cookie
> after signing in. Both frontends do this automatically.

---

## Roles

`IsAdminRole` and `IsCustomerRole` read `user.role` from the database row. The
session also records the role it was opened with; if the account's role changes,
`UmsSessionAuthentication` flushes the session rather than granting stale rights.

| Role | Can reach |
|---|---|
| ADMIN | `/api/admin/*`, admin commerce endpoints |
| CUSTOMER | `/api/customer/*`, cart, orders, addresses, wishlist |
| anonymous | catalogue, store settings, banners, guest cart |

---

## Settings

```python
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7          # 7 days
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False                   # the SPA must read it
CSRF_COOKIE_SAMESITE = "Lax"
AUTHENTICATION_BACKENDS = ["apps.authentication.backends.OTPBackend"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.authentication.authentication.UmsSessionAuthentication",
    ],
}
```

`SameSite=Lax` rather than `Strict`: a top-level navigation into the store must
still carry the cookie, or the shopper arrives looking signed out.

---

## Frontend

Neither dashboard stores a credential. `localStorage` holds only a display
summary (`ums.auth.user`, `ums.admin.user`) so the header does not flicker. Any
key left by an older build (`ums.auth.access`, `ums.admin.refresh`, …) is purged
on boot and asserted absent by the browser suite.

```js
axios.create({ baseURL, withCredentials: true })
```

The 401 rule is strict and lives in one place per app: **only a 401 from an
account endpoint may sign a user out.** A 403 is a permission or CSRF answer, a
5xx is the server having a bad day, and a network error means we do not know.
None of those are evidence that a session ended.

---

## Operational notes

- **Cleanup:** `python manage.py clearsessions` (cron daily). Expired rows are
  ignored by Django but keep growing otherwise.
- **Multi-worker:** `blacklist_all_for_user` walks live session rows, so it sees
  sessions created by any worker. (The round-29 rotation cache was per-process;
  this is not.)
- **`AUTH_DEV_MODE`** returns `dev_otp` in responses. It must be off anywhere
  reachable.
- **Authorization gap:** the customer/order/address/payment viewsets still do not
  enforce permissions — see [`SECURITY_POSTURE.md`](../SECURITY_POSTURE.md). That
  is separate from authentication and is still open.
