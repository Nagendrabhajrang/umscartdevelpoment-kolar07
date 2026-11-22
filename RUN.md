# Running UMS Mart on your own machine

A tested, step-by-step guide. Total time: about 10 minutes.

The project has **three parts** that run as three separate processes:

| Part | What it is | Address |
|---|---|---|
| API | Django + PostgreSQL | http://127.0.0.1:8000 |
| Customer storefront | React (Vite) | http://localhost:5173 |
| Admin console | React (Vite) | http://localhost:5174 |

You need **all three running at once** for a working storefront. The two front
ends talk to the API, so start the API first.

---

## 0. Install the prerequisites

| Tool | Version needed | Check it with |
|---|---|---|
| **Python** | 3.11 or newer | `python --version` |
| **Node.js** | 20 or newer (18 works) | `node --version` |
| **PostgreSQL** | 14 or newer | `psql --version` |

> **SQLite is not supported.** This project uses PostgreSQL-only features.
> The database is not optional — the API will not start without it.

If `python --version` shows 3.10 or lower, install a newer Python. On Windows
use the python.org installer and **tick "Add Python to PATH"**.

---

## 1. Unzip the project

Extract `ums_mart.zip` somewhere with **no spaces and no non-English characters
in the path**, for example:

- Windows: `C:\Users\<you>\Desktop\ums_mart`
- macOS / Linux: `~/ums_mart`

You should end up with `README.md`, `backend/`, `frontend/`, `deployment/`,
`docs/` and `run_smoke.py` directly inside that folder.

---

## 2. Create the database

### Windows (using pgAdmin or the SQL Shell)

Open **SQL Shell (psql)** from the Start menu, press Enter through the prompts,
then type your postgres password and run:

```sql
CREATE ROLE ums_mart_user WITH LOGIN PASSWORD '1234' CREATEDB;
CREATE DATABASE ums_mart_db OWNER ums_mart_user;
\q
```

`CREATEDB` matters — the test suite creates a temporary database.

### macOS / Linux

```bash
sudo -u postgres psql
```

```sql
CREATE ROLE ums_mart_user WITH LOGIN PASSWORD '1234' CREATEDB;
CREATE DATABASE ums_mart_db OWNER ums_mart_user;
\q
```

On macOS with Homebrew, `psql postgres` usually works without `sudo -u postgres`.

---

## 3. Create the `.env` file

The `.env` is **deliberately not shipped inside the ZIP** (it holds secrets).
Copy the template instead.

**Windows (cmd):**

```cmd
cd C:\Users\<you>\Desktop\ums_mart
copy .env.example backend\.env
```

**Windows (PowerShell), macOS, Linux:**

```bash
cd ~/ums_mart
cp .env.example backend/.env
```

Now open `backend/.env` in any text editor and change **only these three lines**:

```ini
DB_NAME=ums_mart_db
DB_USER=ums_mart_user
DB_PASSWORD=1234
```

Those must match exactly what you created in step 2. The template already
ships with `1234`, so if you ran the CREATE ROLE above unchanged there is
nothing to edit here.

> You do **not** need to touch `MEDIA_ROOT`, `STATIC_ROOT` or any path. They
> are computed from the code, so the project works from any folder. Leave the
> `CORS_ALLOWED_ORIGINS` line empty too — the dev servers proxy requests, so no
> CORS setup is needed.

---

## 4. Install the Python dependencies

From the repo root (the folder containing `README.md`):

**Windows (cmd):**

```cmd
cd C:\Users\<you>\Desktop\ums_mart
python -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
```

**macOS / Linux:**

```bash
cd ~/ums_mart
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

You should see `(venv)` at the start of your prompt afterwards.

> **PowerShell says "running scripts is disabled"?** Run this once, then retry:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

---

## 5. Build the database tables and demo data

```bash
cd backend
python manage.py migrate
python manage.py seed_data
```

Expected end of the seed output:

```
  Orders         : 16
  Payments       : 16
  Tickets        : 2
  Images         : 32 product, 3 banner
```

You now have 32 products, 4 customers, 16 orders and 16 payments to click
through.

Optional — a Django admin login at `/admin/`:

```bash
python manage.py createsuperuser
```

---

## 6. Start the API

```bash
python manage.py runserver
```

Leave this terminal open. Check it works by opening:

- **http://127.0.0.1:8000/health/** → should say `"database": "up"`
- **http://127.0.0.1:8000/api/docs/** → interactive Swagger documentation

---

## 7. Start the customer storefront

**Open a second terminal** (leave the API running) and activate the venv again
only if you need Python — for npm you do not.

**Windows (cmd):**

```cmd
cd C:\Users\<you>\Desktop\ums_mart\frontend\customer-web
npm install
npm run dev
```

**macOS / Linux:**

```bash
cd ~/ums_mart/frontend/customer-web
npm install
npm run dev
```

Open **http://localhost:5173**.

`npm install` takes a minute the first time. No `.env` needed — the dev server
already forwards `/api` and `/media` to port 8000.

---

## 8. Start the admin console

**Open a third terminal:**

```cmd
cd C:\Users\<you>\Desktop\ums_mart\frontend\admin-dashboard
npm install
npm run dev
```

```bash
cd ~/ums_mart/frontend/admin-dashboard
npm install
npm run dev
```

Open **http://localhost:5174**.

---

## You should now have

| Terminal | Command | URL |
|---|---|---|
| 1 | `python manage.py runserver` | http://127.0.0.1:8000/api/docs/ |
| 2 | `npm run dev` (customer-web) | http://localhost:5173 |
| 3 | `npm run dev` (admin-dashboard) | http://localhost:5174 |

The storefront header lets you pick which demo shopper you are (Aarav, Diya,
Kabir, Meera). Switching shoppers switches the cart, orders and wishlist.

---

## Optional: run the test suites

With the API **still running**:

```bash
# from the repo root - real HTTP, 122 checks
python run_smoke.py

# Django unit tests, 373 tests (API server can stay up)
cd backend
python manage.py test

# front-end contract suite, 145 checks (needs API running)
cd ../frontend
python frontend_e2e.py
```

The UI screenshot suite additionally needs Playwright:

```bash
pip install playwright
python -m playwright install chromium
python ui_smoke.py both
```

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `connection to server at "127.0.0.1", port 5432 failed` | PostgreSQL is not running. Start the service (`services.msc` on Windows, `brew services start postgresql` on macOS, `sudo systemctl start postgresql` on Linux). |
| `password authentication failed for user "ums_mart_user"` | The password in `backend/.env` does not match the one you set in step 2. Fix the role: `ALTER ROLE ums_mart_user WITH PASSWORD 'newpass';` then update `.env`. |
| `FATAL: database "ums_mart_db" does not exist` | Step 2 did not complete. Re-run the `CREATE DATABASE` line. |
| `ModuleNotFoundError: No module named 'django'` | The venv is not activated, or `pip install` was run from the wrong folder. Run `pip install -r backend/requirements.txt` from the repo root with `(venv)` visible in your prompt. |
| `'python' is not recognized` (Windows) | Python is not on PATH. Reinstall with "Add Python to PATH" ticked, or use `py` instead of `python`. |
| Port 8000 already in use | Another server is running. Use `python manage.py runserver 8001` and update `frontend/*/vite.config.js` proxy targets to 8001. |
| Vite says port 5173 is in use | It automatically moves to 5174/5175 — just use the URL it prints. |
| Frontend loads but every list is empty | The API is not running, or it crashed. Check terminal 1. |
| Product images are broken | `media/` was not generated. Run `python manage.py seed_data` from `backend/`. |
| `psql: command not found` (macOS) | `brew install postgresql@17` then add its `bin` to PATH. |

---

## What this build does and does not do

| | |
|---|---|
| Payments | **Cash on delivery only.** UPI was removed — its endpoints return `400 upi_not_enabled` |
| Support tickets | **Removed.** Customers get a Help & contact page (phone, email, address, FAQ) |
| Deliveries | "Mark as delivered" is **disabled until the cash is recorded** |
| Authentication | **None.** Keep it on localhost |

## Important limitation

**There is no authentication in this build.** Every endpoint — including admin
create/update/delete and the media files — is open to anyone who can reach it.
Requests are identified by an `X-Customer-Id` header, which is a development
seam, not a security boundary.

Keep this on `localhost`. Do not expose it to the internet or a shared network
with `AUTH_DEV_MODE` on: `send-otp` returns the code in the response. Sessions are implemented (`docs/AUTHENTICATION.md`); the open item is authorization on the commerce viewsets (`SECURITY_POSTURE.md`).
