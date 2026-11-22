# UMS Mart — complete local setup, start to finish

Everything from installing the tools to clicking through a running store.
Written for **Windows** (your machine) with macOS/Linux differences noted.
Time: about 20 minutes on a first run.

Commands in this guide are for **PowerShell** unless a block says `cmd`.
Your prompt starting with `PS` means you are in PowerShell.

---

## What you are setting up

Three programs that run at the same time:

| # | Program | What it does | Address |
|---|---|---|---|
| 1 | Django API + PostgreSQL | all the data and business rules | http://127.0.0.1:8000 |
| 2 | Customer storefront | the shopping site | http://localhost:5173 |
| 3 | Admin console | staff screens | http://localhost:5174 |

The two front ends read from the API, so **the API must be running first**.

Path used throughout: `C:\Users\user\Desktop\mono\ums_mart`
Substitute your own if you unzipped elsewhere.

---

# PART 1 — Install the prerequisites (once)

## 1.1 Python

Install **Python 3.11 or newer** from python.org.

On the first installer screen tick **"Add python.exe to PATH"** — this is the
step people skip and then wonder why `python` is not recognised.

Verify:

```powershell
python --version
```

Expect `Python 3.12.x` or `3.13.x`. If you see an error or the Microsoft Store
opens, reinstall with the PATH box ticked.

## 1.2 Node.js

Install the **LTS** build from nodejs.org (v20 or newer).

```powershell
node --version
npm --version
```

Expect `v20.x` / `v22.x` and `10.x`.

## 1.3 PostgreSQL

Install **PostgreSQL 14 or newer** from postgresql.org. The installer asks you
to set a **superuser (`postgres`) password** — write it down.

Leave the port at **5432** and let it install the command-line tools.

Verify:

```powershell
psql --version
```

If `psql` is not recognised, add `C:\Program Files\PostgreSQL\17\bin` to PATH
and reopen the terminal.

> **SQLite will not work with this project.** PostgreSQL is required.

---

# PART 2 — Get the project on disk

Unzip `ums_mart.zip` to a path with **no spaces and no special characters**.

Good: `C:\Users\user\Desktop\mono\ums_mart`
Bad:  `C:\Users\user\Desktop\my projects\ums mart (final)\`

Inside the folder you should see `backend`, `frontend`, `deployment`, `docs`,
`README.md`, `RUN.md`, `run_smoke.py`.

Open PowerShell there:

```powershell
cd C:\Users\user\Desktop\mono\ums_mart
```

---

# PART 3 — Create the database (once)

Open **SQL Shell (psql)** from the Start menu. Press Enter through the prompts
(defaults are correct), type the `postgres` password you set during install.

You will see a `postgres=#` prompt. Run these two commands:

```sql
CREATE ROLE ums_mart_user WITH LOGIN PASSWORD '1234' CREATEDB;
CREATE DATABASE ums_mart_db OWNER ums_mart_user;
```

`CREATEDB` matters — the test suite creates a temporary database.

Exit:

```sql
\q
```

### Why `1234`

`backend/.env` ships with `DB_PASSWORD=1234` so a local install works with no
edits. It is a development password, only reachable on your own machine. If you
prefer a different one, use it in both places:

```sql
ALTER ROLE ums_mart_user WITH PASSWORD 'your-new-password';
```

then set `DB_PASSWORD=your-new-password` in `backend\.env` (Part 4).

---

# PART 4 — Create the backend `.env`

The `.env` holds secrets, so it is **not inside the ZIP**. Copy the template:

```powershell
cd C:\Users\user\Desktop\mono\ums_mart
copy .env.example backend\.env
```

Open `backend\.env` in Notepad (`notepad backend\.env`) and check these four
lines:

```ini
DJANGO_SETTINGS_MODULE=config.settings.development
DB_NAME=ums_mart_db
DB_USER=ums_mart_user
DB_PASSWORD=1234
```

If you ran Part 3 unchanged, **nothing needs editing**.

> Do **not** touch `MEDIA_ROOT`, `STATIC_ROOT` or `CORS_ALLOWED_ORIGINS`.
> Paths are computed from the code, and the dev servers proxy `/api`, so no
> CORS setup is needed. Those lines exist only for production.

---

# PART 5 — Set up Python and the database tables

## 5.1 Create a virtual environment

From the repo root:

```powershell
cd C:\Users\user\Desktop\mono\ums_mart
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Your prompt now starts with `(venv)`.

**If PowerShell says "running scripts is disabled":**

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Answer `Y`, reopen the terminal, activate again. (Or use `cmd` and run
`venv\Scripts\activate.bat`, which is not blocked.)

## 5.2 Install the Python packages

```powershell
pip install -r backend\requirements.txt
```

Installs Django, DRF, psycopg (PostgreSQL driver), Pillow and the rest —
about 21 packages.

**If you see `getaddrinfo failed` or `ECONNRESET`:** that is your network or
DNS, not the project. Retry, or if you are behind a proxy:

```powershell
pip install -r backend\requirements.txt --index-url https://pypi.org/simple
```

## 5.3 Create the tables

```powershell
cd backend
python manage.py migrate
```

You should see ~15 `Applying ... OK` lines ending with
`Applying sessions.0001_initial... OK`.

## 5.4 Load the demo data

```powershell
python manage.py seed_data
```

Expected output:

```
  Categories     : 20
  Products       : 32
  Customers      : 4
  Promotions     : 4
  Banners        : 3
  Orders         : 16
  Payments       : 16
  Images         : 32 product, 3 banner
```

That also generates all the product artwork into `backend/media/`. Without it
every image is a broken icon.

---

# PART 6 — Start the API

You are in `backend\` with `(venv)` active:

```powershell
python manage.py runserver
```

Leave this window open. Check it in a browser:

- **http://127.0.0.1:8000/** (landing page with live counts) or **http://127.0.0.1:8000/health/** → `{"status":"ok", ..., "database":"up"}`
- **http://127.0.0.1:8000/api/docs/** → Swagger, with all 109 endpoints

If the health page says `"database": "up"`, your database connection is
correct and everything after this will work.

---

# PART 7 — Start the customer storefront

**Open a second PowerShell window** (the API keeps running in the first).

```powershell
cd C:\Users\user\Desktop\mono\ums_mart\frontend\customer-web
npm install
npm run dev
```

`npm install` takes a minute and downloads ~210 packages.

**If you see `ECONNRESET` during `npm install`:** the download broke. Retry
with:

```powershell
npm install --fetch-retries=5 --fetch-retry-mintimeout=20000
```

**If it fails with `EPERM` and leaves `node_modules` behind:**

```powershell
Remove-Item -Recurse -Force node_modules
npm cache clean --force
npm install
```

Then pause Windows Security real-time protection if it keeps locking files.

When it finishes, Vite prints:

```
  VITE v5.4.9  ready in 812 ms
  ➜  Local:   http://localhost:5173/
```

Open **http://localhost:5173**.

---

# PART 8 — Start the admin console

**Open a third PowerShell window.**

```powershell
cd C:\Users\user\Desktop\mono\ums_mart\frontend\admin-dashboard
npm install
npm run dev
```

Vite will pick 5174 because 5173 is taken — use the URL it prints.
Open it: indigo sidebar, dashboard with live figures.

---

# PART 9 — Check everything works

You should now have three windows:

| Window | Running | URL |
|---|---|---|
| 1 | `python manage.py runserver` | http://127.0.0.1:8000/api/docs/ |
| 2 | `npm run dev` (customer-web) | http://localhost:5173 |
| 3 | `npm run dev` (admin-dashboard) | http://localhost:5174 |

### Storefront checklist

- Hero banner **"Fresh groceries in 45 minutes"**
- 10 category circles, product rails with colourful tiles (not broken images)
- **32 products** across the site
- Shopper switcher in the header: Aarav / Diya / Kabir / Meera
- Add something to the cart → a **red count badge** appears on the cart icon
  and on the product tile
- Checkout shows **Cash on delivery only** (no UPI)
- Help & contact page at `/help` with phone, email, address and FAQ

### Admin checklist

- Dashboard: **16 orders**, ~**₹8.1K revenue**, **4 customers**, Payment split
  shows **COD 16 / UPI 0**
- Sidebar shows red counters on **Orders (2)** and **Payments (4)**
- Inventory → the toggle icon flips a row to **Untracked** and back
- Payments: every row says **CASH ON DELIVERY**; the tab reads
  **Cash to collect**
- Orders: **Mark as delivered** is greyed out until the payment is recorded

---

# PART 10 — Running it again later

Nothing needs reinstalling. Three windows, three commands:

**Window 1:**

```powershell
cd C:\Users\user\Desktop\mono\ums_mart\backend
..\venv\Scripts\Activate.ps1
python manage.py runserver
```

**Window 2** and **Window 3:**

```powershell
cd C:\Users\user\Desktop\mono\ums_mart\frontend\customer-web
npm run dev
```

```powershell
cd C:\Users\user\Desktop\mono\ums_mart\frontend\admin-dashboard
npm run dev
```

### Launch all three from one window

```powershell
cd C:\Users\user\Desktop\mono\ums_mart
start "API" cmd /k "cd backend && ..\venv\Scripts\activate && python manage.py runserver"
start "Store" cmd /k "cd frontend\customer-web && npm run dev"
start "Admin" cmd /k "cd frontend\admin-dashboard && npm run dev"
```

### Resetting the demo data

```powershell
cd backend
..\venv\Scripts\Activate.ps1
python manage.py seed_data --flush
```

`--flush` wipes orders, payments, tickets, products and categories and rebuilds
them. Use it any time the data looks wrong.

---

# PART 11 — Optional: run the test suites

The API must be running for the smoke and contract suites.

```powershell
# 117 real HTTP checks (from the repo root)
cd C:\Users\user\Desktop\mono\ums_mart
python run_smoke.py

# 326 Django unit tests
cd backend
python manage.py test

# 165 front-end contract checks (needs the API up)
cd ..\frontend
python frontend_e2e.py
```

Screenshot regression (needs Playwright, once):

```powershell
pip install playwright
python -m playwright install chromium
cd frontend
python ui_smoke.py both
```

---

# Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `connection to server at "127.0.0.1", port 5432 failed` | PostgreSQL is not running. Start the service: `net start postgresql-x64-17` (check the exact name in `services.msc`). |
| `password authentication failed for user "ums_mart_user"` | `.env` password ≠ the role's. Fix: `ALTER ROLE ums_mart_user WITH PASSWORD '1234';` |
| `FATAL: database "ums_mart_db" does not exist` | Part 3 did not complete. Re-run the `CREATE DATABASE` line. |
| `'python' is not recognized` | Python is not on PATH. Reinstall with the checkbox ticked, or use `py`. |
| `running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `ModuleNotFoundError: No module named 'django'` | venv not active, or pip ran from the wrong folder. `(venv)` must be in your prompt. |
| `No module named 'config'` | You are not inside `backend\`. |
| `npm` not recognised | Node is not installed or not on PATH. Reinstall the LTS build. |
| `ECONNRESET` in `npm install` | Network dropped. Retry with `--fetch-retries=5`. |
| `EPERM ... unlink node_modules\...` | Antivirus holds file handles. Pause real-time protection, delete `node_modules`, retry. |
| Vite: `failed to load config ... vite\index.js` | `npm install` did not finish. Delete `node_modules`, reinstall. |
| Port 8000 already in use | Another server is running. `python manage.py runserver 8001`, then edit the proxy target in both `vite.config.js` files. |
| Front end loads but lists are empty | The API is not running — check window 1. |
| Product images are broken | `backend/media/` is empty. Run `python manage.py seed_data`. |
| Cart badge never appears | Add to cart failed — check the API window for a 4xx. Refresh the page. |

---

# The one real limitation

**There is no authentication in this build.** Every endpoint — including admin
create/update/delete and the media files — is open to anyone who can reach the
port. Requests identify the shopper with an `X-Customer-Id` header, which is a
development seam, not a security boundary.

Keep it on `localhost`. Do not put it on a LAN, a shared machine, or the
internet with `AUTH_DEV_MODE` on: `send-otp` returns the code in the response. Authentication and sessions *are* implemented (see `docs/AUTHENTICATION.md`); what is missing is **authorization** on the commerce viewsets (`SECURITY_POSTURE.md`).

### What this build does and does not include

| Feature | Status |
|---|---|
| Cash on delivery | ✅ the only payment method |
| UPI payments | ❌ removed — endpoints return `400 upi_not_enabled` |
| Support tickets | ❌ removed — replaced by the Help & contact page |
| Deliveries | ✅ gated: cannot mark delivered until the cash is recorded |
| Cart / wishlist / orders / coupons / inventory / banners / settings | ✅ all working |
| Login | ❌ none, by design |
