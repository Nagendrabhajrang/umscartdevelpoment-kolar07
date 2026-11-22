# Tomorrow — pick up here

## Status
- Tables: migrated ✅ · seed + admin created ✅
- Admin login: works on **http://localhost:5174** (use this, not the LAN IP)
- Blocked on: saving in admin over LAN IP → 403 `csrf_failed`
- Open decision: **P1 + P3** patch approved in discussion, **not applied yet**

## Approved work (say "do it")
| Step | File | Effect |
|---|---|---|
| P1a | `frontend/admin-dashboard/src/services/adminAuthService.js` | `ensureCsrf({ force })` |
| P1b | `frontend/admin-dashboard/src/services/api.js` | on `csrf_failed` → refresh token → retry once |
| P1c | `backend/common/exceptions.py` | name real cause (origin vs stale) + `details.reason` |
| P3a | `frontend/admin-dashboard/src/components/common/AdminRoute.jsx` | redirect unless `role === "ADMIN"` |
| P3b | catalog / orders / customers viewsets | `IsAdminRole` on writes, reads stay public |

Then: 377 tests · `manage.py check` · both `npm run build` · rebuild zip.

## Fastest unblock right now (no code)
1. Admin at `http://localhost:5174` (already trusted, no `.env` edit)
2. Storefront signed-in on the same machine → use a **separate browser profile**, not another tab
3. Cookies ignore ports: `localhost:5173` and `:5174` share one session

## Your setup
- DB: `ums_mart_databaseadmin` / `ums_mart_useradminums` / `1234` @ `127.0.0.1:5432`
- Venv: `C:\Users\user\Desktop\mono\ums_mart\venv` → use `.\venv\Scripts\python.exe`
- Admin login: `admin` / `UMSMart@Admin2026`
- OTP limits for testing: `OTP_MAX_REQUESTS_PER_HOUR=50`, `OTP_RESEND_COOLDOWN_SECONDS=5`

## Known traps
- `backend\.env` is read **only at server start** — always restart `runserver` after editing
- `CSRF_TRUSTED_ORIGINS` is an **override**, not an addition — repeat localhost/127.0.0.1 entries
- Hosting: use **two subdomains** (`umsmart.com` + `admin.umsmart.com`). Never `umsmart.com/admin` — same host = same cookie jar = this exact bug.
