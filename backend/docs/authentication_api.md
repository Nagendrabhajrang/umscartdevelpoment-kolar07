# UMS Mart — Authentication API

Complete reference for the authentication module: two independent login
workflows (admin and customer), **Django session handling**, and OTP policy.

> **Round 30:** authentication is Django's session framework. There are no JWT
> access or refresh tokens, no `/api/auth/token/refresh/`, and nothing
> token-shaped is returned by any endpoint. The credential is an HttpOnly
> `ums_mart_sessionid` cookie. See `../../docs/AUTHENTICATION.md`.

Base URL in local development: `http://127.0.0.1:8000`

All request and response bodies are JSON. All responses carry
`Cache-Control: no-store` so credentials never sit in a browser or proxy cache.

---

## 1. Design rules

These are enforced in code, not by convention:

| Rule | Where it holds |
|---|---|
| Admin and customer logins are separate flows with no shared form or logic | `/api/admin/*` vs `/api/customer/*`, distinct services |
| No session is created until MFA is verified | `admin_verify_mfa` is the only admin path that calls `login()` |
| Exactly one admin exists, created only by a management command | `manage.py create_admin`; no registration endpoint |
| Customer accounts are created on first successful OTP | `customer_verify_otp` |
| One mobile number maps to one account | `canonical_mobile()` normalisation + unique constraint |
| OTPs are hashed, single-use, expiring, and never logged | `OTPVerification`, `otp_service` |
| Exactly one active session per user | `UserSession.start_new()` revokes the previous one |
| Roles are decided server-side | `IsAdminRole` / `IsCustomerRole` permission classes |
| Password reset revokes every session | `admin_reset_password` |

### OTP policy

| Setting | Default | Env var |
|---|---|---|
| Length | 6 digits | `OTP_LENGTH` |
| Validity | 300 s | `OTP_VALIDITY_SECONDS` |
| Resend cooldown | 60 s | `OTP_RESEND_COOLDOWN_SECONDS` |
| Max verification attempts | 5 | `OTP_MAX_ATTEMPTS` |
| Requests per account per hour | 5 | `OTP_MAX_REQUESTS_PER_HOUR` |
| Requests per IP per hour | 20 | `OTP_MAX_REQUESTS_PER_IP_PER_HOUR` |

Codes are stored as a salted hash. A code is invalidated when it is used, when a
newer code supersedes it, when it expires, or when its attempt budget is spent.

### Mobile number normalisation

Every accepted spelling resolves to one canonical form, so a returning customer
never gets a second account:

| Input | Stored as |
|---|---|
| `9876543210` | `+919876543210` |
| `09876543210` | `+919876543210` |
| `+919876543210` | `+919876543210` |
| `919876543210` | `+919876543210` |
| `98765 43210` | `+919876543210` |

Valid input is `+91` followed by ten digits beginning 6–9.

### Error format

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "Invalid username or password.",
    "details": {},
    "status": 401
  }
}
```

Common codes: `invalid_credentials`, `otp_invalid`, `otp_expired`,
`otp_already_used`, `otp_attempts_exhausted`, `otp_resend_cooldown`,
`rate_limit_exceeded`, `invalid_mobile_number`, `not_authenticated`,
`permission_denied`, `validation_error`.

---

## 2. Admin workflow

### 2.1 `POST /api/admin/login/`

Step one. Verifies the password and emails an OTP. **Returns no tokens.**

```json
{ "username": "admin", "password": "UMSMart@Admin2026" }
```

`200 OK`

```json
{
  "mfa_required": true,
  "email_hint": "nag********@gmail.com",
  "message": "A verification code has been sent to your email.",
  "expires_in": 300,
  "dev_otp": "017818"
}
```

`dev_otp` appears only when `AUTH_DEV_MODE` and `DEBUG` are both true.

`401 Unauthorized` — `invalid_credentials`. The same response is returned for an
unknown username and a wrong password.

### 2.2 `POST /api/admin/verify-mfa/`

Exchanges the emailed code for a token pair. This is the only place admin tokens
are created.

```json
{ "code": "017818" }
```

`200 OK`

```json
{
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi...",
  "user": {
    "id": 1,
    "role": "ADMIN",
    "username": "admin",
    "email": "nagendrajoe@gmail.com",
    "display_name": "Store Admin"
  },
  "session_id": "7f830be0-7a77-4c47-88f9-739923724af1"
}
```

Failures: `400` with `otp_invalid`, `otp_expired`, `otp_already_used`, or
`otp_attempts_exhausted`.

### 2.3 `POST /api/admin/resend-mfa-otp/`

Issues a fresh code for a pending MFA challenge. Subject to the 60-second
cooldown and hourly caps.

```json
{ "username": "admin" }
```

### 2.4 `POST /api/admin/forgot-password/`

```json
{ "email": "nagendrajoe@gmail.com" }
```

`200 OK` — always the same message and status, whether or not the address is
registered:

```json
{ "message": "If that email is registered, a reset code has been sent." }
```

### 2.5 `POST /api/admin/verify-reset-otp/`

```json
{ "email": "nagendrajoe@gmail.com", "code": "483920" }
```

`200 OK` → `{ "reset_token": "...", "expires_in": 600 }`

The reset token is separate from the OTP, single-use, and valid for 10 minutes.

### 2.6 `POST /api/admin/reset-password/`

```json
{
  "reset_token": "...",
  "new_password": "BrandNewPass!2026",
  "confirm_password": "BrandNewPass!2026"
}
```

On success every session row for the account is **deleted**, so any browser
holding an old cookie is signed out immediately (round 30: this is a stronger
guarantee than the old token blacklist, which only stopped future issuance).

### 2.7 `POST /api/admin/change-password/otp/`

Authenticated. Sends a confirmation code to the admin's email before a password
change.

### 2.8 `POST /api/admin/change-password/`

Authenticated.

```json
{
  "current_password": "UMSMart@Admin2026",
  "code": "551204",
  "new_password": "AnotherPass!2026",
  "confirm_password": "AnotherPass!2026"
}
```

### 2.9 `POST /api/admin/logout/`

Authenticated. Calls `logout()`, deleting the session row and clearing the
cookie. Other devices are untouched — use `/api/auth/logout-all/` for those.

---

## 3. Customer workflow

### 3.1 `POST /api/customer/send-otp/`

Step one. Sends an SMS OTP. No account is created yet.

```json
{ "mobile_number": "9876543210" }
```

`200 OK`

```json
{
  "message": "A verification code has been sent to your mobile.",
  "mobile_hint": "+9198XXXX3210",
  "expires_in": 300,
  "is_new_customer": true,
  "dev_otp": "786901"
}
```

### 3.2 `POST /api/customer/verify-otp/`

Verifies the code and **creates the account on first success**.

```json
{ "mobile_number": "9876543210", "code": "786901" }
```

`200 OK`

```json
{
  "is_new_customer": true,
  "user": {
    "id": 4,
    "role": "CUSTOMER",
    "mobile_number": "+919876543210",
    "display_name": "+919876543210",
    "customer_id": 67
  },
  "cart_merge_pending": true
}
```

No token is returned. The session id lives in the `ums_mart_sessionid` cookie
(HttpOnly, `Path=/`, seven days) and is never readable by JavaScript.

**The guest cart is not merged by this call.** If the request carries
`X-Guest-Cart`, the response reports `cart_merge_pending: true` and the basket is
folded in by the *first authenticated cart request* instead
(`GET /api/v1/cart/`). That request proves the session cookie actually came back;
merging here would move the items into an account the browser might be unable to
reach — the cookie-blocked / cross-site-frame case, which silently emptied the
cart on sign-in. Clients should therefore call `GET /api/v1/cart/` after a
successful verify and expect the merged basket in that response.

If the browser refuses the session cookie, `GET /api/auth/session/` keeps
answering `401`. Clients must treat that as "not signed in" and must **not**
discard a guest cart key on the strength of a 200 from this endpoint alone.

### 3.3 `POST /api/customer/resend-otp/`

```json
{ "mobile_number": "9876543210" }
```

Subject to the same cooldown and hourly caps.

### 3.4 `GET /api/customer/profile/` · `PUT` · `PATCH`

Authenticated, customer role only.

```json
{
  "id": 4,
  "role": "CUSTOMER",
  "mobile_number": "+919876543210",
  "is_mobile_verified": true,
  "display_name": "+919876543210",
  "customer_id": 67
}
```

### 3.5 `POST /api/customer/logout/`

Authenticated. Ends the current session.

---

## 4. Shared endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/auth/csrf/` | Plant the CSRF cookie the SPA needs before any unsafe request. |
| `GET` | `/api/auth/session/` | **200** = signed in (body carries the user) / **401** = no session. |
| `GET` | `/api/auth/session/status/` | Same, but always 200 with `authenticated: bool`. |
| `POST` | `/api/auth/logout-all/` | Delete every session row for this account. |
| `GET` | `/api/auth/session/` | Inspect the current session. |
| `POST` | `/api/auth/logout-all/` | Revoke every session for the caller. |

### Refresh

```json
{ "refresh": "eyJhbGciOi..." }
```

`200 OK` → `{ "access": "...", "refresh": "..." }`. Reusing a rotated token
returns `401`.

### Session

```json
{
  "authenticated": true,
  "role": "ADMIN",
  "user_id": 1,
  "session_id": "7f830be0-...",
  "device_information": "Mozilla/5.0 ...",
  "created_at": "2026-11-09T09:12:44Z",
  "last_activity": "2026-11-09T09:20:02Z",
  "expires_at": "2026-11-16T09:12:44Z"
}
```

---

## 5. Token claims

The session stores:

| Key | Meaning |
|---|---|
| `_auth_user_id` | Primary key of `accounts.User` (Django) |
| `_auth_user_backend` | `apps.authentication.backends.OTPBackend` |
| `_auth_user_hash` | Lets a password change invalidate the session |
| `ums_role` | `ADMIN` or `CUSTOMER`, pinned at login |

`ums_role` is what makes a role change safe: if the account's role no longer
matches the value the session was opened with, `UmsSessionAuthentication`
**flushes the session** and the request proceeds anonymously (401 on a protected
route) rather than granting the old rights.

Nothing about the session is sent to the client. `/api/auth/session/` reports
`expires_at` and `age_seconds`, plus the user — never the session key.

---

## 6. Trying it in Postman

1. Import as a collection or create the requests by hand. Set a collection
   variable `base_url = http://127.0.0.1:8000`.
2. **Admin.** `POST {{base_url}}/api/admin/login/` with the credentials above.
   Copy `dev_otp` from the response.
3. `POST {{base_url}}/api/admin/verify-mfa/` with `{"code": "<that code>"}`.
   Copy `access`.
4. On later requests add the header
   the HttpOnly `ums_mart_sessionid` cookie that the browser sends by itself.
5. **Customer.** `POST {{base_url}}/api/customer/send-otp/` with
   `{"mobile_number": "9876543210"}`, then `verify-otp` with `dev_otp`.
6. In Postman, a **Tests** script can capture tokens automatically:

```javascript
const body = pm.response.json();
if (body.access) pm.collectionVariables.set("access", body.access);
if (body.refresh) pm.collectionVariables.set("refresh", body.refresh);
```

Remember that signing in twice revokes the earlier session — the first token
starts returning `401` by design.

---

## 7. Provisioning the admin

```bash
python manage.py create_admin \
  --username admin \
  --email nagendrajoe@gmail.com \
  --password 'UMSMart@Admin2026'
```

The command refuses to create a second admin and runs Django's password
validators. Use `--rotate` to change the existing admin's password.

---

## 8. Testing

```bash
# Django suite (includes 35 authentication tests)
python manage.py test

# Live HTTP end-to-end run against a running server
python scripts/e2e_auth_check.py
```

The E2E script writes housekeeping rows only to the auth tables; commerce data is
untouched.
