# Run UMS Mart locally — copy-paste runbook

**Repo:** `C:\Users\user\Desktop\mono\ums_mart`
Windows · PowerShell · PostgreSQL 14+

You need **three windows open at once**: API (`:8000`), storefront (`:5173`), admin (`:5174`).

| # | Step | Window | Time |
|---|---|---|---|
| 1 | PostgreSQL running | — | 1 min |
| 2 | `backend\.env` | — | 1 min |
| 3 | venv + deps | 1 | 5 min |
| 4 | migrate + seed | 1 | 2 min |
| 5 | start API | 1 | keep open |
| 6 | storefront + admin | 2, 3 | 2 min |

---

## Stage 1 — PostgreSQL

```powershell
Get-Service postgresql*
```

`Status : Running` → good. If `Stopped`:

```powershell
Start-Service postgresql-x64-17   # adjust the version number to yours
```

Login works?

```powershell
$env:PGPASSWORD="1234"
psql -h 127.0.0.1 -U ums_mart_useradminums -d ums_mart_databaseadmin -c "SELECT current_database(), current_user;"
```

Expected: `ums_mart_databaseadmin | ums_mart_useradminums`

> Role/database don't exist yet? Run the SQL in `TABLE_CREATION_GUIDE.md` → Step 1.

---

## Stage 2 — `backend\.env`

```powershell
cd C:\Users\user\Desktop\mono\ums_mart
Test-Path backend\.env
```

`False` → create it:

```powershell
@"
DJANGO_SETTINGS_MODULE=config.settings.development
SECRET_KEY=local-dev-only-change-me-to-a-long-random-string
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=ums_mart_databaseadmin
DB_USER=ums_mart_useradminums
DB_PASSWORD=1234
DB_HOST=127.0.0.1
DB_PORT=5432
AUTH_DEV_MODE=True
EMAIL_CONSOLE_FALLBACK=True
ADMIN_EMAIL=admin@example.com
OTP_MAX_REQUESTS_PER_HOUR=50
OTP_RESEND_COOLDOWN_SECONDS=5
"@ | Set-Content -Encoding ASCII backend\.env
```

Already exists → make sure it has **no** `DATABASE_URL` line (it overrides `DB_*`):

```powershell
Select-String -Path backend\.env -Pattern "DATABASE_URL"
```
Nothing printed = correct.

**Prove Django reads it:**

```powershell
.\venv\Scripts\python.exe backend\manage.py shell -c "from django.conf import settings as s; d=s.DATABASES['default']; print(d['NAME'], d['USER'], d['HOST'])"
```

---

## Stage 3 — virtualenv + dependencies

```powershell
cd C:\Users\user\Desktop\mono\ums_mart
Test-Path .\venv\Scripts\python.exe
```

`False` → create it:

```powershell
py -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

`True` → still verify the packages are present:

```powershell
.\venv\Scripts\python.exe -c "import django, rest_framework, psycopg, dotenv; print('deps ok')"
```

> Use `.\venv\Scripts\python.exe` everywhere — no activation needed, no ExecutionPolicy problems.

---

## Stage 4 — tables + data

```powershell
.\venv\Scripts\python.exe backend\manage.py migrate
```

Expect a wall of `Applying … OK`. **Re-run until it prints "No migrations to apply."**

```powershell
.\venv\Scripts\python.exe backend\manage.py seed_data --flush
.\venv\Scripts\python.exe backend\manage.py create_admin --username admin --email admin@example.com --password "UMSMart@Admin2026"
```

Admin already exists? Reset its password instead:

```powershell
.\venv\Scripts\python.exe backend\manage.py create_admin --username admin --email admin@example.com --password "UMSMart@Admin2026" --rotate
```

---

## Stage 5 — API  *(window 1, leave open)*

```powershell
cd C:\Users\user\Desktop\mono\ums_mart
.\venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000
```

Checkpoint — open <http://127.0.0.1:8000/health/> → `"database": "up"`.

Any error here means `.env`/PostgreSQL; nothing downstream can fix it.

---

## Stage 6 — the two front ends

**Window 2 — storefront**
```powershell
cd C:\Users\user\Desktop\mono\ums_mart\frontend\customer-web
npm install
npm run dev
```

**Window 3 — admin console**
```powershell
cd C:\Users\user\Desktop\mono\ums_mart\frontend\admin-dashboard
npm install
npm run dev
```

`npm install` only needs re-running after the folder is replaced.

---

## Open these

| App | URL | Login |
|---|---|---|
| Storefront | http://localhost:5173 | any seeded mobile `+919876500001` … `…04`, OTP shown in the API window / `dev_otp` |
| Admin | http://localhost:5174 | `admin` / `UMSMart@Admin2026`, then the emailed OTP (printed in the API window) |
| API health | http://127.0.0.1:8000/health/ | — |

**Do not use `http://10.78.40.39:5174` yet.** `changeOrigin: true` is still in `vite.config.js`, so writes from the LAN IP are rejected by the CSRF Origin check.

**Both roles at once?** Admin on `localhost:5174`, customer on `127.0.0.1:5173`. Different host → different cookies → no overwrite. Two tabs in the same browser is otherwise one identity (cookies ignore ports).

---

## Quick fixes

| Symptom | Fix |
|---|---|
| `fe_sendauth: no password supplied` | `backend\.env` missing `DB_PASSWORD` |
| `password authentication failed` | `.env` name/password ≠ the psql role; check `DB_USER` |
| `permission denied for schema public` | `ALTER DATABASE ums_mart_databaseadmin OWNER TO ums_mart_useradminums;` |
| `database … does not exist` | run `CREATE DATABASE` (Stage 1 of the table guide) |
| `python` opens Microsoft Store | use `py` or `.\venv\Scripts\python.exe` |
| `venv\Scripts\activate` not recognized | PowerShell needs `.\venv\Scripts\Activate.ps1`, or skip activation |
| **"Too many verification requests"** | `DELETE FROM auth_otp_throttle;` in psql, then retry |
| "Please wait N seconds" | OTP cooldown — use `OTP_RESEND_COOLDOWN_SECONDS=5` |
| Admin save → "security token expired" | you're on the LAN IP; use `localhost:5174`, or set `changeOrigin: false` |
| Port already in use | `netstat -ano \| findstr :8000` then `taskkill /PID <pid> /F` |

---

## Stop everything

In each window: **Ctrl+C**. PostgreSQL can keep running.
