# Sign-in sessions, cookies, and the preview iframe

*Why the storefront said "this browser blocked the sign-in cookie" and what was changed.*

## Symptom

After a correct OTP the customer page showed:

> We couldn't complete sign-in because this browser blocked the sign-in cookie.
> Your cart is still saved here. Allow cookies for this site, then try again.

The OTP was accepted (200 from `POST /api/customer/verify-otp/`), but the very next
call, `GET /api/auth/session/`, answered **401**, so the SPA concluded no session
existed and raised `session_cookie_blocked`
(`frontend/customer-web/src/context/AuthContext.jsx`).

## Root cause (two layers)

1. **The API was running the wrong settings module.** `backend/manage.py` did

   ```python
   os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
   ```

   *before* Django imported settings. `config/settings/base.py` does load
   `backend/.env`, but by then the module name was already fixed, so
   `DJANGO_SETTINGS_MODULE=config.settings.sandbox` in `.env` was silently ignored
   and the process ran **development** settings. Development sets
   `SESSION_COOKIE_SAMESITE="Lax"`; only `sandbox` enables the
   `COOKIE_CROSS_SITE` block (`SameSite=None; Secure`).

2. **A cross-site iframe drops `Lax` cookies.** The hosted preview renders the
   storefront inside an iframe whose parent is a different site, so the browser
   treats our cookies as third-party. `SameSite=Lax` cookies are never sent there —
   hence the 401 on the very first authenticated request.

   Proof at HTTP level: `curl -D - http://127.0.0.1:5173/api/auth/csrf/` used to
   return `ums_mart_csrftoken=…; SameSite=Lax`; it now returns
   `…; SameSite=None; Secure`.

## Fix 1 — `.env` really selects the settings module

`backend/manage.py` loads `backend/.env` with `python-dotenv` **before** the
`setdefault` call, so the file's `DJANGO_SETTINGS_MODULE` wins for real
(`override=False`, so a shell variable still takes precedence). Nothing else about
the settings layout changed.

## Fix 2 — bearer session fallback (`AUTH_BEARER_FALLBACK`)

`SameSite=None` is necessary but not sufficient: Chrome's third-party cookie
restrictions, Safari's default cookie policy, and any "block all cookies" setting
will still refuse the session cookie inside a cross-site frame. So the API now can
hand the client the session key itself:

| Piece | Where |
|---|---|
| Setting, default **off** | `config/settings/base.py` → `AUTH_BEARER_FALLBACK = env_bool("AUTH_BEARER_FALLBACK", False)` |
| Switching it on | `config/settings/sandbox.py` → `AUTH_BEARER_FALLBACK = True` (development/production untouched) |
| Login/verify responses | `apps/authentication/services/session_service.py::attach_session_token()` — adds `session_token` to the payload **only** when the flag is on; wired into `CustomerVerifyOTPView` and `AdminVerifyMFAView` |
| Authentication | `apps/authentication/authentication.py::UmsSessionAuthentication` — tries `Authorization: Bearer <session key>` first, resolves it through Django's `SessionStore` (so it is the *same* session row the cookie would have used), still enforces the role pin (`SESSION_ROLE_KEY`), and skips CSRF for that path |
| Logout | `session_service.end_session()` — deletes the bearer session row, so a copied token dies on sign-out |
| Customer SPA | `services/authService.js`: stores the token under `ums.auth.bearer` on verify, sends the header, skips the CSRF round-trip while it holds one, clears it in `logout()`'s `finally`; `services/api.js` adds the header to every axios call |
| Admin SPA | same pattern in `services/adminAuthService.js` (`ums.admin.bearer`) and `services/api.js` |

The cookie path is untouched and still preferred in normal same-origin browsing:
`AUTH_BEARER_FALLBACK=False` everywhere except this sandbox, so production behaviour
is unchanged.

## How it was verified

Headless Chromium, parent shell `http://localhost:9999/parent.html` embedding the
storefront in `<iframe sandbox="allow-scripts allow-forms allow-same-origin">`
(the cross-site case):

| Check | Result |
|---|---|
| OTP login inside the cross-site iframe | signed in, no "blocked cookie" message |
| `/api/auth/session/` after wiping **all** cookies (bearer only) | **200** — the account page keeps working with zero cookies |
| Same-origin login at `http://127.0.0.1:5173/` (cookie path, regression) | signed in |
| Logout | `ums.auth.bearer` cleared and the old token returns **401** (row deleted) |
| Admin console login (`admin` + MFA) | dashboard reached, `ums.admin.bearer` stored |
| `manage.py test --parallel 4` | **390 tests, OK** |
| `vite build` (customer + admin) | exit 0 |

Note: a *fully* sandboxed frame (no `allow-same-origin`) is not testable with the
Vite dev server — the opaque `null` origin blocks the ES-module scripts by CORS.
The preview keeps `allow-same-origin`, which is what these tests reproduce.

## Ops notes

- Server changes need a restart: the API runs with `--noreload`.
- To reproduce a real "cookie refused" browser, delete cookies from the page
  (`document.cookie` / DevTools) after login — the session must survive on the
  bearer token alone.
- OTP requests are throttled per user (5/hour, `apps/authentication/services/otp_service.py`,
  `OTPThrottle`). Repeated test logins will hit `otp_rate_limited`; clear the
  `authentication.OTPThrottle` rows for the demo customer before a fresh run
  (user id **6**, `+919876500001`).
- If a shopper still lands on the "browser refused to keep the sign-in session"
  message, both the cookie **and** client storage are blocked — that is a browser
  policy decision, not a server bug.

## Security notes on the fallback

- The token is the Django session key, so it grants exactly what the cookie would.
  It is only issued when `AUTH_BEARER_FALLBACK` is on (this sandbox), never in
  `development` or `production`.
- It is stored in `localStorage`, which is readable by any script on the page — the
  same trust boundary the SPA already has, but it means an XSS is slightly worse than
  with an `HttpOnly` cookie. Keep the flag off on the real deployment and rely on the
  cookie there.
- It lives and dies with the server-side session: expiry, the role pin, and logout
  (which deletes the row) all apply unchanged.

---

# "Your security token expired" (CSRF)

That sentence is `common/exceptions.py` answering a **CSRF rejection**
(`code: "csrf_failed"`, HTTP 403) from a session-authenticated write. It has
nothing to do with the sign-in session — the user stays signed in — but it was
one message covering three different problems, and the only advice was "refresh".

## What it can actually mean

The interceptor now reads DRF's CSRF detail and returns `details.reason`:

| `details.reason` | Real cause | What to do |
|---|---|---|
| `token_mismatch` | The `X-CSRFToken` header and the `ums_mart_csrftoken` cookie disagree — a token rotated by a sign-in in another tab, a restored session, or a stale header built before Django rotated it. | Nothing: the client re-fetches and replays automatically. |
| `token_missing` | The browser sent no CSRF cookie at all (site data blocked, cookie cleared, wrong host). | Allow cookies/site data for the site. |
| `origin_mismatch` | The `Origin` header is not in `CSRF_TRUSTED_ORIGINS` — a new port, a LAN IP, an ngrok host, or the storefront served from somewhere the API does not know. | Add that origin to `CSRF_TRUSTED_ORIGINS` in `.env` and restart the API. |

Verify from a shell (Django's own test client, so nothing is cached):

```bash
cd backend && ../.venv/bin/python - <<'PY'
import os, django, json
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.sandbox")
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
from apps.authentication.services.session_service import SESSION_ROLE_KEY
U = get_user_model(); u = U.objects.filter(mobile_number="+919876500001").first()
c = Client(enforce_csrf_checks=True); c.force_login(u)
s = c.session; s[SESSION_ROLE_KEY] = u.role; s.save(); c.get("/api/auth/csrf/")
good = c.cookies["ums_mart_csrftoken"].value
body = json.dumps({"full_name": "Aarav"})
for label, tok, extra in [("wrong", "x"*32, {}), ("missing", None, {}),
                          ("bad origin", good, {"HTTP_ORIGIN": "http://evil.example.com"})]:
    h = {"HTTP_X_CSRFTOKEN": tok} if tok else {}; h.update(extra)
    r = c.patch("/api/customer/profile/update/", data=body,
                content_type="application/json", **h)
    print(label, r.status_code, r.json()["error"]["details"]["reason"])
PY
```

## What changed so it stops happening

1. **The API names the cause** (`details.reason` + a specific sentence) instead of
   one generic line, so the failure is diagnosable without a debugger.
2. **Both SPAs heal a stale token themselves.** On `csrf_failed` for an unsafe
   request the axios interceptor deletes the cookie, fetches `/api/auth/csrf/`
   again and replays the request **once**. The old behaviour — telling a shopper
   or an admin to press refresh — is gone. A second failure is reported normally,
   because by then the cookies really are blocked.
3. **The customer auth client always echoes the token** when the cookie exists,
   even while a bearer token is in play. A stale bearer (issued before the
   database was reset) makes the server fall back to cookie auth, and that path
   needs the header — skipping it was a self-inflicted `csrf_failed`.

Verified in headless Chromium by faking one 403 from the API:

| App | Sequence observed |
|---|---|
| Storefront (add to cart) | `POST /api/v1/cart/items/ → 403` → `GET /api/auth/csrf/ → 200` → `POST /api/v1/cart/items/ → 201`, no error shown |
| Admin (save store profile) | `PATCH /api/v1/store-settings/ → 403` → `GET /api/auth/csrf/ → 200` → `PATCH → 200`, no error shown |

Backend suite after the change: **390 tests, OK**.

## Development origins (round 40)

`CSRF_TRUSTED_ORIGINS` cannot express "any port on this machine". A dev server
that landed on a different port (5174 busy -> 5175), or a phone opening the
store on `http://192.168.x.x:5174`, therefore had every unsafe request rejected
as `origin_mismatch` - the admin console reported it while changing an order
status, which reads like a permissions bug rather than an origin mismatch.

Two changes address it:

* `common.middleware.DevOriginTolerantCsrfMiddleware` subclasses Django's CSRF
  middleware and, **in DEBUG only**, treats loopback and private-network origins
  as verified. `DEBUG = False` (production) keeps the stock, strict behaviour.
  Disable it in a local `.env` with `CSRF_ALLOW_LOCAL_
  ORIGINS=False` if you want to reproduce the strict path.
* an `origin_mismatch` rejection now names the rejected origin and lists the
  origins currently trusted, in both `error.message` and
  `error.details.{origin,trusted_origins}`.

The explicit `CSRF_TRUSTED_ORIGINS` list still matters for anything that is not
a local origin (preview hosts, tunnels, staging domains).
