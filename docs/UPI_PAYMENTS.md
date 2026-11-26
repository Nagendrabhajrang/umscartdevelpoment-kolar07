# UPI payments — how it works end to end

The store takes **cash on delivery** or **UPI**. Both are configured by the admin
at runtime; nothing here needs a redeploy.

```
Customer                    Storefront                     API                        Admin console
--------                    ----------                     ---                        -------------
picks "UPI — pay now"  -->  shows store QR + UPI ID
                            (from /store-settings/)
places order           -->  POST /orders/checkout/  ---->  Order(payment_method=upi)
                                                            Payment(awaiting_verification)
                                                          Order(payment_status=pending_verification)
scans QR / pays in app
enters UTR + screenshot -->  POST /payments/{id}/submit-proof/  -->  Payment(pending)
                                                                     Order stays pending_verification
                                                          <----  Payments -> "UPI to verify"
                                                                 matches bank statement
                                                                 POST /payments/{id}/approve/
                                                            Payment(paid), Order(payment_status=paid)
```

A rejection (`POST /payments/{id}/reject/`) puts the payment back to `rejected`,
the order to `unpaid`, and the storefront shows the admin's reason with the form
reopened so the customer can resubmit.

## Where the QR and UPI ID come from

`StoreSettings` (singleton, editable in **Admin → Settings → Payments**) holds:

| Field | Meaning |
|---|---|
| `cod_enabled` | offer cash on delivery at checkout |
| `upi_enabled` | offer UPI at checkout |
| `upi_id` | the store's VPA, e.g. `umsmart@okhdfcbank` |
| `upi_payee_name` | name shown inside the UPI app |
| `upi_qr_image` | the QR PNG customers scan |

Two ways to get the QR image:

1. **Upload** an export from GPay / PhonePe / Paytm (Settings → UPI QR image).
2. **Generate it** — type the UPI ID and press *Generate QR from UPI ID*. The
   backend renders a real, scannable QR of the standard intent
   (`upi://pay?pa=…&pn=…&cu=INR`) via the `segno` library:

   ```bash
   ./sandbox_up.sh --setup            # or, directly:
   cd backend && ../.venv/bin/python manage.py generate_upi_qr
   cd backend && ../.venv/bin/python manage.py generate_upi_qr --amount 250 --note UMS-2026-0001
   ```

   Regenerating replaces the previous PNG instead of accumulating copies.

`seed_data` calls the same generator, so a fresh seed already has a working QR.
If `upi_enabled` is on but `upi_id` is empty, checkout refuses the UPI option with
`upi_not_configured` rather than creating an unpayable order.

## API surface

| Endpoint | Who | What |
|---|---|---|
| `GET /api/v1/store-settings/` | storefront | UPI ID, payee name, `upi_qr_image_url`, `cod_enabled`, `upi_enabled` |
| `PATCH /api/v1/store-settings/` | admin | update the fields above (multipart when uploading a QR) |
| `POST /api/v1/store-settings/upi-qr/` | admin | draw a fresh QR from the saved UPI ID |
| `GET /api/v1/payments/{id}/upi-details/` | customer | amount, UPI ID, QR URL, status, `can_submit`, `rejection_reason` |
| `POST /api/v1/payments/{id}/submit-proof/` | customer | `transaction_reference` (+ optional name, UPI ID, screenshot) → `pending` |
| `POST /api/v1/payments/{id}/approve/` | admin | `paid` + order `paid` |
| `POST /api/v1/payments/{id}/reject/` | admin | `rejected` + reason + order `unpaid` |
| `GET /api/v1/payments/pending-verification/` | admin | the UPI queue (`awaiting_verification` **and** `pending`, UPI only) |
| `POST /api/v1/payments/{id}/cod-collected/` | admin | the cash equivalent |

Every state change writes a `PaymentVerification` row, so the audit trail of a
payment is: `submitted` (checkout) → `submitted`/`resubmitted` (customer) →
`approved` or `rejected` (admin).

## Screens

**Customer**
- Checkout → *Payment method*: radio cards for **Cash on delivery** and
  **UPI — pay now** (each hidden if the store switched it off). Picking UPI opens
  the QR, the UPI ID with a copy button, the payee, the amount and an
  *Open in UPI app* deep link.
- Order page (UPI orders) → the same panel plus **I have paid — confirm the
  reference** (UTR, name, your UPI ID, optional screenshot). Status banners:
  *Waiting for your UPI payment* → *under review* → *Payment received*, or
  *We could not match that payment* + the reason and the form back.
- The order list and Help FAQ mention both methods.

**Admin**
- Settings → Payments: enable/disable each method, edit UPI ID and payee, upload
  or generate the QR.
- Payments → **UPI to verify** tab: one card per payment with the reference,
  payer, screenshot, and Approve / Reject / Review. The other tabs stay
  cash-only (Cash to collect) or show everything with a Method column.
- Orders → the payment chip shows `UPI`; an unpaid UPI order's primary action is
  **Verify UPI payment**, which deep-links into the verification panel.
- Dashboard's *Payment methods* card splits COD vs UPI counts.

## Tests

`apps/payments/tests/test_payments.py::UpiPaymentTests` covers checkout →
reference → approve, rejection → resubmit, the two configuration guards
(`upi_disabled`, `upi_not_configured`), the queue filtering, and the guards that
stop UPI-only operations from running on a cash payment.

```bash
cd backend && ../.venv/bin/python manage.py test apps.payments apps.orders apps.store_settings
cd backend && ../.venv/bin/python manage.py test          # 390 tests, all green
```

## Not done yet

- **Mobile app** (`mobile/ums_mart_customer`) — untouched. Its `PaymentMethod`
  enum is Flutter-side and will need the `upi` member plus the QR screen when we
  pick mobile up.
- **Automatic reconciliation** — approval is manual, by design: no payment
  gateway, no webhook. If you later add one (Razorpay/Cashfree), the webhook can
  call the same `approve_payment` service.

---

## Round 39 — the confirmation flow, tightened

**Customer side**

- **Checkout shows UPI whenever the store can take it.** The option is offered when
  `upi_enabled` is true *or* a UPI ID exists; only an explicit
  `upi_enabled: false` hides it (an older settings row without the flag no longer
  silently hides UPI). Picking UPI renders the box with the store QR, the UPI ID +
  copy button, payee, amount and the `upi://pay` deep link.
- **The transaction ID is a popup, not an inline form.** After the order exists,
  `UpiReferenceModal` opens with a single text box for the transaction ID / UTR
  (plus optional payer name, payer UPI and screenshot). It opens **automatically the
  first time** the order page is visited while the payment is still awaiting a
  reference, and afterwards from the *“I have paid — enter transaction ID”* button.
- Submitting writes the reference to the payment row (`POST
  /payments/{id}/submit-proof/` → `transaction_id` + `PaymentVerification` history,
  payment → `pending`, order → `pending_verification`) and the box switches to
  “Payment submitted — under review”.

**Admin side**

- Payments → **UPI to verify**: the green action is now labelled **“Confirm UPI
  payment”** (it was “Approve”); it stays disabled until the customer has submitted
  a reference. Confirming sets the payment to `paid` and the order's
  `payment_status` to `paid`.
- Orders → the **Mark delivered** button is gated by the payment:
  - **UPI**: visible but *disabled* until the payment is confirmed, with the tooltip
    “Confirm this order's UPI payment in Payments first”.
  - **COD**: unchanged — the button appears once the cash is recorded, exactly as
    before.
  The API enforces the same rule (`apps/orders/services.py`), with the message and
  error code now chosen by method: `upi_payment_not_confirmed` for UPI,
  `payment_required_before_delivery` for cash.

Verified end to end in headless Chromium: UPI at checkout → QR + `umsmart@okhdfcbank`
shown → order placed (`UMS-…`) → popup auto-opens → reference `4291000999888777`
saved to the payment → admin confirms → order paid → delivery unlocks. Backend:
390 tests OK; both frontends build.

## Round 41 — the transaction ID is a gate, not a suggestion

A UPI order used to be creatable and then abandonable: the customer was sent to
the order page and the "paste your transaction ID" popup could be dismissed, so
the store ended up holding an order with money it could not match to anything.

Changes:

* **One popup, two fields.** `UpiReferenceModal` now asks for
  `Transaction ID / UTR` (required) and `Phone / Google Pay number`
  (optional - a 10-15 digit mobile number or a UPI handle such as
  `9876543210@ybl`). The payer name, payer UPI ID and screenshot fields were
  removed: the store does not use them to reconcile a credit, and every extra
  field is another reason to abandon the step.
* **It blocks forward.** Directly after a UPI order is created, checkout mounts
  the modal in `blocking` mode: no close button, no backdrop click, no Escape,
  and the submit button stays disabled until the reference is at least 6
  characters. Only on success does checkout navigate to the order page - that is
  the first moment the customer is allowed past this screen. The hint under the
  disabled button says so explicitly: *"Enter the transaction ID to continue to
  your order."*
* **Where it is stored.** `transaction_reference` lands in
  `Payment.transaction_id` (as before) and the optional contact lands in
  `Payment.mobile_number`, which the payment serializer already exposes, so the
  admin Payables view shows both without a schema change - no new migration.
* Reopening the popup from the order page stays dismissible: there the order
  already exists, and trapping someone on a page they are reading would be
  hostile.
