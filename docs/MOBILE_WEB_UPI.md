# UMS Mart — UPI at checkout, in both apps

One patch that puts the same payment behaviour into the two customer-facing
apps, so they can never drift apart again.

* **mobile app** — `mobile/ums_mart_customer` (Flutter)
* **customer web** — `frontend/customer-web` (React + Vite)

**18 files · +976 −85 · base commit `18b5fd2`**

---

## What "the same behaviour" means

1. Checkout offers **Cash on delivery** and **UPI — pay now**, and only the
   options the admin left switched on in the dashboard.
2. Choosing UPI opens a **popup** — the QR is never drawn inline on the page.
3. The popup order is fixed: **QR → transaction ID / UTR → optional PhonePe /
   Google Pay number**.
4. **No reference, no order.** Pressing Place order with UPI and nothing typed
   brings the popup back instead of creating the order.
5. The reference is POSTed to `/api/v1/payments/{id}/submit-proof/` right after
   the order exists; if that call fails, the popup returns as a blocking step.
6. The **order screen never asks again** — it shows the payment state (review,
   paid) and, on mobile, a read-only QR card.
7. COD shows **no QR, no UPI ID, no popup** anywhere.

Backend: no change needed. The QR is the file the admin uploads in
Dashboard → Settings → UPI, and the proof endpoint already existed.

---

## The files

### mobile app — 5 files
| File | Change |
|---|---|
| `lib/models.dart` | store settings gain `upi_id`, `upi_payee_name`, `upi_qr_image_url`, `cod_enabled`, `upi_enabled`; orders gain `payment_method`, `payment_id`, `needsUpiReference` |
| `lib/api.dart` | `checkoutPreview` / `checkout` take the payment method; new `Api.submitUpiProof()` |
| `lib/screens/upi.dart` | **new** — the popup (QR, amount, UPI ID + copy, UTR, optional wallet number) |
| `lib/screens/checkout.dart` | payment picker, reference strip, gate, proof submit, UPI wording on the success screen |
| `lib/screens/orders.dart` | read-only Pay by UPI card on order details |

### customer web — 13 files
| File | Change |
|---|---|
| `src/components/payment/UpiReferenceModal.jsx` | **new** — the popup |
| `src/components/payment/UpiPayBox.jsx` | **new** — QR / UPI ID panel used on the order page |
| `src/services/paymentService.js` | **new** — submit-proof call |
| `src/pages/Checkout/CheckoutPage.jsx` | method picker, gate, proof submit |
| `src/pages/Orders/OrderDetailsPage.jsx` | payment state, no re-entry button |
| `src/components/common/Modal.jsx` | blocking mode (no Esc, no backdrop close) |
| `src/services/api.js`, `src/services/authService.js` | session + proof plumbing |
| `src/context/AuthContext.jsx` | customer session handling |
| `src/pages/Login/LoginPage.jsx`, `src/pages/Help/HelpPage.jsx`, `src/components/layout/FootBar.jsx`, `src/utils/constants.js` | supporting changes from the same round |

---

## Apply

**Double-click `APPLY-MOBILE-WEB.cmd`.** It first checks whether your tree
already has the code and says so instead of failing, then applies the patch,
and falls back to copying the 18 files if the patch does not fit.

Or, by hand, from the repo root:

```
git apply --whitespace=nowarn "C:\Users\user\Downloads\ums-mart-mobile-web-upi.patch"
git --no-pager diff --stat -- mobile frontend/customer-web
```

> If your tree is **already at `6b66a19` or later**, both apps are current and
> `git apply` will report that the patch does not apply. That is expected — the
> code is already there. Use the `.cmd`, which detects this, or just check:
> `findstr UpiReferenceModal frontend\customer-web\src\pages\Checkout\CheckoutPage.jsx`
> and `findstr submitUpiProof mobile\ums_mart_customer\lib\api.dart`.

## Run

```
cd backend && python manage.py runserver
```
```
cd frontend\customer-web && npm install && npm run dev
```
```
cd mobile\ums_mart_customer && flutter pub get && flutter run -d chrome --dart-define=API_BASE=http://127.0.0.1:8000
```

`backend\.env` needs `http://127.0.0.1:8000` and `http://127.0.0.1:5173` in
`CSRF_TRUSTED_ORIGINS`, otherwise the checkout POST is rejected as an untrusted
origin. That is the single most common reason a fresh machine "cannot place an
order".

---

## Verified in the sandbox against this exact patch

The patch was re-applied on a pristine `18b5fd2` worktree; all 18 files came out
**byte-identical** to the tree that ran these orders.

*Mobile (Flutter, run as its web target at 412×880):* checkout → UPI → popup →
UTR `4291000111222333` + `9876500001@ybl` → `POST /orders/checkout/` 201 →
`POST /payments/26/submit-proof/` 200 → order **UMS-20261126-KVRTLZ**, payment
row `upi / pending / transaction_id=4291000111222333`. Place order with UPI and
nothing typed → popup reopens, no order. COD → order
**UMS-20261126-LA0PRB**, no popup, zero proof calls.

*Customer web (React, 1440×900):* same flow in the browser → order
**UMS-20261126-RE8CJS** (`/orders/28`), page reads "Payment submitted — under
review" with the QR and UPI ID, no way to re-enter a reference.

Screenshots of both apps: `showcase/` (mobile) and `showcase/web/` (web).
