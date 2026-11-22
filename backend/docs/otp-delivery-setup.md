# Turning on real OTP delivery

Right now **no SMS and no email is actually sent**. The code is generated
correctly and shown on screen, but nothing leaves the server. This is a
configuration gap, not a code gap.

## About "test mode" — the honest answer

You asked whether these providers have a test API for development. Here is what
each one actually offers:

| Provider | Test mode? | What it really means |
|---|---|---|
| **2Factor** | No separate sandbox endpoint | New accounts get **free test credits**. You send a **real SMS to a real handset** until the credits run out. There is no separate fake-sandbox URL. |
| **Resend** | Yes, in a limited sense | With no verified domain you can send **real email** from `onboarding@resend.dev`, but **only to the address on your own Resend account**. Any other recipient is rejected with 403. |
| **2Factor DLT** | Nothing to do in test | India requires DLT registration to deliver to arbitrary numbers. Test credits usually reach your own number without it; bulk sending needs it. |

So there is no such thing as "send to any mobile without an account". The
practical free path is:

- **SMS** → sign up at 2Factor, use the free test credits to send to **your own**
  number.
- **Email** → sign up at Resend, use `onboarding@resend.dev` to send to **your
  own** address.

That is enough to prove the whole flow end to end, which is what you want.

> **I cannot sign up on your behalf.** Creating a 2Factor or Resend account needs
> your email, phone and acceptance of their terms, and the API keys are issued to
> your account. Five minutes on their site, then paste the keys below.

---

## How to tell what is actually happening

The `send-otp` response tells you, without guessing:

```json
{
  "message": "SMS delivery is not configured on this server. No text message was sent.",
  "delivered": false,
  "dev_otp": "812093"
}
```

| Field | Meaning |
|---|---|
| `delivered: true` | The provider accepted the message. |
| `delivered: false` | Nothing was sent. The reason is in `message`. |
| `dev_otp` | The code, shown only while `AUTH_DEV_MODE=True` and `DEBUG=True`. |

Check the current state at any time:

```powershell
cd backend
python manage.py check_delivery
```

```
OTP delivery configuration

  SMS (2Factor)   NOT CONFIGURED   no SMS will be sent
                  fix: set TWOFACTOR_API_KEY in backend/.env, then restart
  Email           LOCAL OUTBOX ONLY   nothing is sent
                  fix: set RESEND_API_KEY or EMAIL_HOST in backend/.env

Codes in API responses
  AUTH_DEV_MODE   ON   the response includes `dev_otp` so you can sign in without delivery
```

Once the keys are in, the same command can prove delivery with one real message
each — this consumes a credit and a quota unit, so run it deliberately:

```powershell
python manage.py check_delivery --send-to 9876543210 --send-email-to you@gmail.com
```

---

## 1. SMS for customers (2Factor.in)

The mobile path uses 2Factor for delivery. You keep control of the code - 2Factor
is pure transport, which is why the provider is swappable.

### Get the key

1. Sign up at <https://2factor.in>.
2. Open the dashboard and copy the **API key**.
3. Add a sender ID if 2Factor requires one for your account (DLT registration in
   India; 2Factor walks you through it).

### Add it to `backend/.env`

```ini
TWOFACTOR_API_KEY=your-2factor-api-key-here
TWOFACTOR_SENDER_ID=UMSMRT
```

### Restart the API, then send yourself a code

```powershell
# stop the server (Ctrl+C), then:
python manage.py runserver
```

Open <http://localhost:5173/login>, enter **your own** mobile number, and check
the response. With the key set you should see `delivered: true` and the SMS
should arrive within a few seconds.

If `delivered` is still `false`, read `backend/logs` (or the server console) —
the service logs `2Factor rejected the message (status N)` or
`2Factor request failed` with the reason.

### Verify without sending an SMS

Useful for testing the flow without spending credits:

```powershell
cd backend
python -c "import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development'); django.setup(); from apps.notifications.services import sms_service; sms_service.send_otp_sms(mobile_number='+919876500001', code='123456'); print('accepted')"
```

A `SMSDeliveryError` means it is not configured or the provider refused it.

---

## 2. Email for admin MFA and password reset

The admin path sends codes to `nagendrajoe@gmail.com` by email.

### Option A — Resend (recommended for real delivery)

1. Sign up at <https://resend.com> and create an API key.
2. Verify your sending domain, or use their test domain to send to yourself.
3. Add to `backend/.env`:

```ini
RESEND_API_KEY=re_your_key_here
RESEND_FROM_EMAIL=UMS Mart <no-reply@yourdomain.com>
```

### Option B — SMTP (Gmail works)

If `RESEND_API_KEY` is empty the service falls back to SMTP, then to a console
outbox. To use Gmail:

```ini
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=nagendrajoe@gmail.com
EMAIL_HOST_PASSWORD=your-16-character-app-password
```

Gmail requires an **App Password** (Google Account → Security → 2-Step
Verification → App passwords), not your normal password.

### Option C — nothing (current state)

With no key, and `EMAIL_CONSOLE_FALLBACK=True` and `DEBUG=True`, the message is
written to a development outbox instead of being sent. The admin flow still works
because `dev_otp` is in the response.

---

## 3. Turn dev mode off before shipping

`AUTH_DEV_MODE` echoes the code in the API response. It is ignored whenever
`DEBUG=False`, so a production deployment is already protected by the `DEBUG`
guard — but set it explicitly as well:

```ini
DEBUG=False
AUTH_DEV_MODE=False
```

Confirm the codes stop appearing:

```powershell
python -c "import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.production'); django.setup(); from config.settings.base import dev_mode_active; print('dev mode:', dev_mode_active())"
```

Must print `dev mode: False`.

---

## 4. Checklist

- [ ] `TWOFACTOR_API_KEY` set in `backend/.env`
- [ ] API restarted after editing `.env` (settings load once at boot)
- [ ] `send-otp` returns `"delivered": true`
- [ ] SMS arrives on your phone
- [ ] `RESEND_API_KEY` or SMTP set for admin email
- [ ] Admin MFA email arrives
- [ ] `DEBUG=False` and `AUTH_DEV_MODE=False` for any non-local deployment

## Note on `.env` and restarts

Settings are read once when the server starts. Editing `.env` while the server
runs changes nothing until you restart it. This has already cost time twice in
this project.
