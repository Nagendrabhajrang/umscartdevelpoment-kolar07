# UMS Mart — Customer app (Flutter / Android)

The same storefront as `frontend/customer-web`, rebuilt for Android with a
more tactile UI: perspective carousel, tilting product cards, gradient
category tiles and live order tracking.

**The Django API is not modified.** Same endpoints, same session cookie, same
guest-cart header.

---

## 1. Prerequisites

| Tool | Check |
|---|---|
| Flutter 3.19+ (Dart 3.3+) | `flutter --version` |
| Android Studio + SDK | `flutter doctor` |
| A device or emulator | `flutter devices` |

`flutter doctor` should show a green tick for **Android toolchain**.

---

## 2. Point the app at your API

Your machine's LAN IP — **the phone cannot reach `127.0.0.1`**:

```powershell
ipconfig | findstr IPv4
```

Then either edit `lib/core/config.dart` or pass it at build time:

```powershell
flutter run --dart-define=API_BASE=http://192.168.1.38:8000
```

Defaults baked in:

| Target | Base URL |
|---|---|
| Android emulator | `http://10.0.2.2:8000` (the host's loopback) |
| iOS simulator / web | `http://127.0.0.1:8000` |
| Physical device | pass `--dart-define` |

---

## 3. Let Django accept the phone

In `backend\.env` (then **restart `runserver`** — it only reads `.env` at boot):

```ini
ALLOWED_HOSTS=*
CSRF_TRUSTED_ORIGINS=http://192.168.1.38:8000,http://localhost:8000,http://127.0.0.1:8000
```

Start the API so it listens on the LAN, not just loopback:

```powershell
.\venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000
```

Allow the ports through Windows Firewall if the phone cannot connect:

```powershell
New-NetFirewallRule -DisplayName "UMS Dev" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

> **Why `CSRF_TRUSTED_ORIGINS`?** The app's HTTP client has no browser
> `Origin` header, so Django's CSRF check passes by construction — but any
> request carrying a `Referer` from a non-trusted host would be rejected.
> Listing the API origin costs nothing and removes a whole class of 403s.

---

## 4. Run

```powershell
cd C:\Users\user\Desktop\mono\ums_mart\mobile\ums_mart_customer
flutter pub get
flutter run -d <device-id>
```

First build takes a few minutes (Gradle). Hot reload: press `r`.

If `android/` ever gets out of sync with your Flutter version, regenerate it
(this **keeps** `lib/`):

```powershell
flutter create . --platforms=android
```

---

## 5. Log in

| | |
|---|---|
| Mobile | any seeded number, e.g. `+919876500001` |
| OTP | printed in the API window **and** echoed into the login screen as a "Dev OTP" banner (only while `AUTH_DEV_MODE=True`) |

The session is an HttpOnly cookie held in a persisted cookie jar, so it survives
an app restart — the same seven days the web build gets.

---

## What is implemented

| Area | Screens |
|---|---|
| Browse | Home (hero carousel, categories, trending, new arrivals), Categories, Products grid, Search, Product details |
| Basket | Add/increment/decrement/remove, coupon apply/remove, live bill from `/cart/summary/` |
| Auth | Mobile + OTP, resend with cooldown, dev OTP banner, sign out |
| Checkout | Saved addresses, add address, COD, order notes, server-priced preview, place order |
| Orders | List with status filters, **20 s live poll**, detail with timeline, cancel |

Guest → account basket merge happens inside `verify-otp`, exactly as on the web.

---

## File map

```
lib/
  main.dart                     app + provider stack + boot
  core/
    config.dart                 API base URL per platform
    api_client.dart             Dio + cookie jar + CSRF + error shape
    services.dart               every endpoint the app uses
    app_theme.dart              colours, gradients, component themes
  models/models.dart            thin JSON wrappers
  state/
    auth_state.dart             session (cookie), OTP flow
    cart_state.dart             basket, guest key, totals
  widgets/
    common.dart                 TiltCard (real 3D), shimmer, pills, money
    product_card.dart           card + ADD/stepper
    hero_carousel.dart          perspective carousel, 5 s auto-advance
  screens/
    splash → home_shell (bottom nav) → home / categories / orders / profile
    product_details, products, search, cart, checkout,
    address_form_sheet, login, order_details
```

---

## Things to know

1. **Cookies are the whole ballgame.** If you ever replace `dio` with plain
   `http`, logins will silently stop sticking — the cookie jar is what keeps
   the Django session alive.
2. **CSRF.** Unsafe methods must echo `ums_mart_csrftoken` in `X-CSRFToken`.
   `api_client.dart` reads it out of the jar and sets the header; do not remove
   that interceptor.
3. **The app never prices an order.** Totals come from the API. If a number
   looks wrong, the fix is server-side.
4. **Live status is polling.** 20–25 s while the screen is visible, paused when
   the app is backgrounded. True push would need WebSockets/SSE, which the
   backend does not expose yet.
5. **Cleartext HTTP** is enabled in `AndroidManifest.xml` for development.
   Remove `android:usesCleartextTraffic="true"` and serve HTTPS before release.

## Two ways to run it

### 1. Live preview / any browser (same-origin proxy)

```bash
flutter build web --release --dart-define=API_BASE=relative
python3 serve_web.py          # http://localhost:8099
```

`serve_web.py` serves `build/web` and forwards `/api` and `/media` to
`http://127.0.0.1:8000`, so the browser talks to a single origin and the
HttpOnly session cookie behaves exactly like it does on the phone.
Override the upstream with `API_UPSTREAM=...`.

### 2. Android (the real target)

```bash
# emulator: 10.0.2.2 is the host machine's loopback, the default API_BASE
flutter run

# physical handset on the same Wi-Fi: use the PC's LAN IP
flutter build apk --release --dart-define=API_BASE=http://192.168.1.38:8000
```

A release build with no `API_BASE` shows a "Almost there" screen naming the
command, instead of silently failing to connect to 10.0.2.2.

## API routes the app uses

| Purpose | Path |
| --- | --- |
| Send / resend / verify OTP | `/api/customer/send-otp/`, `/api/customer/verify-otp/` |
| Session, CSRF, logout | `/api/auth/session/`, `/api/auth/csrf/`, `/api/customer/logout/` |
| Catalogue | `/api/v1/catalog/products/`, `.../categories/`, `.../featured/` |
| Basket | `/api/v1/cart/`, `/api/v1/cart/items/`, `/api/v1/cart/coupon/` |
| Orders | `/api/v1/orders/mine/`, `/api/v1/orders/<id>/`, `.../cancel/` |
| Addresses, wishlist | `/api/v1/addresses/mine/`, `/api/v1/wishlist/` |

## Note on the sample artwork

The seeded catalogue images (`/media/catalog/products/*.png`) are generated
gradient tiles with the product initials — that is what `seed_data` writes, so
the "AS", "IG", "BC" tiles in the app are the real files, not a placeholder
fallback. Drop real product photos in the same folders (same filenames) and they
appear in both the web storefront and the app with no code change.
