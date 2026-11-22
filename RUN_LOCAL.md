# Run UMS Mart on your own machine

A corrected guide. `RUN.md` in this repo is out of date in three places that
will actually block you — see [What changed since RUN.md](#what-changed-since-runmd)
at the bottom.

**Time:** ~15 minutes the first time (most of it `npm install`).

You need **three processes running at once**:

| Part | Tech | URL |
|---|---|---|
| API | Django + PostgreSQL | http://127.0.0.1:8000 |
| Customer storefront | React + Vite | http://localhost:5173 |
| Admin console | React + Vite | http://localhost:5174 |

The two front ends proxy `/api` and `/media` to port 8000, so start the API
**first** and leave it running.

---

## 0. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.11+ (3.13 tested) | `python --version` |
| Node.js | 18+ (20 recommended) | `node --version` |
| PostgreSQL | 14+ | `psql --version` |

> **SQLite is not supported.** The API will not start without PostgreSQL.

### Windows: getting `python` to work

If typing `python` opens the Microsoft Store, or prints:

```
Python was not found; run without arguments to install from the Microsoft Store,
or disable this shortcut from Settings > Apps > Advanced app settings >
App execution aliases.
```

…then Python is **not installed** (or is not on PATH). That message is a Windows
placeholder, not an error from Python. Two ways out, in order of preference:

**1 — Install the real thing (recommended).** Download Python 3.11 or newer from
<https://www.python.org/downloads/windows/> and **tick "Add python.exe to PATH"**
on the first installer screen. Then close and reopen your terminal.

**2 — Turn off the alias so it stops lying to you.** Settings → Apps → Advanced
app settings → App execution aliases → switch **off** both `python.exe` and
`python3.exe`. Now `python` reports "not recognized" honestly instead of opening
a store page. This does *not* install Python — you still need step 1.

**Until Python is on PATH, use the `py` launcher**, which the python.org
installer adds automatically and which Windows reserves for exactly this case:

```cmd
py --version            :: should print 3.11 or higher
py -m venv venv
venv\Scripts\activate
py -m pip install -r backend\requirements.txt
```

Every `python ...` command in this guide becomes `py ...` on such a machine.
Once the venv is active, `python` works normally inside it — the venv provides
its own `python.exe`, which bypasses the Store alias entirely.

Verify before going further:

```
> py --version
Python 3.13.5
```

If that prints 3.10 or lower, install a newer Python — the project requires
**3.11+** (it is developed and tested on 3.13).

---

## 1. Unzip

Extract `ums_mart.zip` to a path with **no spaces and no non-English
characters**:

- Windows: `C:\Users\<you>\Desktop\ums_mart`
- macOS / Linux: `~/ums_mart`

You should see `backend/`, `frontend/`, `deployment/`, `docs/`, `README.md` and
`run_smoke.py` directly inside it. All commands below assume this folder is the
current directory.

---

## 2. Start PostgreSQL

```bash
# Windows (run as Administrator, in cmd)
net start postgresql-x64-17

# macOS (Homebrew)
brew services start postgresql@17

# Linux
sudo systemctl start postgresql && sudo systemctl status postgresql
```

Confirm it is listening:

```bash
psql --version
```

---

## 3. Create the database and role

Open a psql shell as the superuser:

```bash
# macOS / Linux
sudo -u postgres psql      # on macOS Homebrew: psql postgres

# Windows
psql -U postgres           # entered via SQL Shell (psql) from the Start menu
```

Then run:

```sql
CREATE ROLE ums_mart_user WITH LOGIN PASSWORD '1234' CREATEDB;
CREATE DATABASE ums_mart_db OWNER ums_mart_user;
\q
```

**`CREATEDB` is required** — the Django test suite creates a temporary database.

### If the database already exists

`CREATE DATABASE` fails with `already exists` and people skip it — which is how
`permission denied for schema public` happens later. The role can connect but
does not own the database, and since **PostgreSQL 15** the `public` schema no
longer grants CREATE to every user.

Run this instead. It is idempotent and safe whether the role and database exist
or not:

```sql
-- connect to the maintenance DB first
\c postgres

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ums_mart_user') THEN
    CREATE ROLE ums_mart_user WITH LOGIN PASSWORD '1234' CREATEDB;
  ELSE
    ALTER ROLE ums_mart_user WITH LOGIN PASSWORD '1234' CREATEDB;
  END IF;
END
$$;

-- make the role own the database outright (fixes the schema permission issue)
ALTER DATABASE ums_mart_db OWNER TO ums_mart_user;

\q
```

Then, connecting **as** `ums_mart_user` to `ums_mart_db`:

```sql
GRANT ALL ON SCHEMA public TO ums_mart_user;
\q
```

Both statements are belt-and-braces: ownership alone is enough on PostgreSQL 15+,
because the `public` schema is owned by `pg_database_owner`, so whoever owns the
database can create in it. The explicit `GRANT` covers the case where someone
removed that default.

Verify with:

```sql
-- as ums_mart_user, in ums_mart_db
CREATE TABLE _probe(x int);
DROP TABLE _probe;
```

If that runs without error, `migrate` will work.

### Using different database names

If you picked your own names, use them consistently in **both** places — the SQL
and `backend/.env` must match exactly, including case.

Example: `ums_mart_datab` / `ums_mart_useradmin` / password `1234`.

```sql
-- as the postgres superuser
\c postgres

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ums_mart_useradmin') THEN
    CREATE ROLE ums_mart_useradmin WITH LOGIN PASSWORD '1234' CREATEDB;
  ELSE
    ALTER ROLE ums_mart_useradmin WITH LOGIN PASSWORD '1234' CREATEDB;
  END IF;
END
$$;

CREATE DATABASE ums_mart_datab OWNER ums_mart_useradmin;
ALTER DATABASE ums_mart_datab OWNER TO ums_mart_useradmin;
```

Then `backend/.env`:

```ini
DB_NAME=ums_mart_datab
DB_USER=ums_mart_useradmin
DB_PASSWORD=1234
DB_HOST=127.0.0.1
DB_PORT=5432
```

This combination was verified end to end: `migrate` applied all migrations,
`/health/` reported `"database": "up"`, and `manage.py test` ran **377 tests,
OK** (the role's `CREATEDB` is what lets the test runner build its own database).

> **`DB_PASSWORD` has no default.** If it is empty or absent, Django sends an
> empty password and PostgreSQL rejects the login. It must be present and match
> the `CREATE ROLE` line exactly.
>
> **Do not set `DATABASE_URL` as well.** It takes precedence over every `DB_*`
> variable, so a stale `DATABASE_URL` will make correct-looking credentials seem
> ignored.

---

## 4. Create `backend/.env`

The `.env` is deliberately **not** shipped in the zip (it holds secrets).

```bash
# macOS / Linux / PowerShell
cp .env.example backend/.env

# Windows cmd
copy .env.example backend\.env
```

The template already matches the role you just created, so **no edits are
needed** for a local run. If you changed the password in step 3, update these
three lines in `backend/.env`:

```ini
DB_NAME=ums_mart_db
DB_USER=ums_mart_user
DB_PASSWORD=1234
```

Leave `CORS_ALLOWED_ORIGINS` empty. The Vite dev server proxies every request,
so no CORS configuration is needed.

> **Do not set `COOKIE_CROSS_SITE=1` locally.** That flag exists only for the
> HTTPS preview host. Over plain `http://localhost` a `SameSite=None; Secure`
> cookie is silently dropped by the browser, which would make you appear signed
> out on every request. Leave it unset.

---

## 5. Install Python dependencies

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

```cmd
:: Windows cmd
python -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
```

Your prompt should now start with `(venv)`.

<details>
<summary>PowerShell says "running scripts is disabled"</summary>

Run once, then retry:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
</details>

---

## 6. Create the tables and demo data

```bash
cd backend
python manage.py migrate
python manage.py seed_data
```

Expected tail of the output:

```
Demo data ready.
  Categories     : 6
  Products       : 32
  Customers      : 4
  Orders         : 16
  Payments       : 16
```

`seed_data` is idempotent — running it twice does not duplicate anything. Use
`python manage.py seed_data --flush` to wipe and rebuild the demo data.

---

## 7. Create the admin account

There is exactly **one** admin in this system and no public signup. Provision it
from the shell:

```bash
python manage.py create_admin
```

It prompts for a password. To change it later:

```bash
python manage.py create_admin --rotate
```

> The admin login is **username + password + an email OTP**. No SMTP server is
> configured locally, so the email is never actually sent. Instead the code comes
> back in the API response as `dev_otp`, and that is the **only** place it
> appears — it is not written to the console. To read it, open the admin login
> page, press F12 → **Network**, submit the username and password, click the
> `login/` request and look at its **Response** for `dev_otp`. Paste those six
> digits into the MFA field.
>
> The same applies to customer login: `dev_otp` is in the `send-otp/` response.

---

## 8. Start the API

Still inside `backend/` with the venv active:

```bash
python manage.py runserver
```

Leave this terminal open. Verify:

- http://127.0.0.1:8000/health/ → `{"status": "ok", "database": "up"}`
- http://127.0.0.1:8000/api/docs/ → interactive API documentation

> Bind address matters only if you need LAN access. Plain `runserver` binds
> `127.0.0.1`, which is correct for a local machine.

---

## 9. Start the storefront

**New terminal.** You do not need the venv here.

```bash
cd ~/ums_mart/frontend/customer-web      # Windows: cd ...\frontend\customer-web
npm install
npm run dev
```

Open **http://localhost:5173**.

---

## 10. Start the admin console

**Third terminal.**

```bash
cd ~/ums_mart/frontend/admin-dashboard
npm install
npm run dev
```

Open **http://localhost:5174** and sign in with the account from step 7.

---

## You are up when

| Terminal | Command | URL |
|---|---|---|
| 1 | `python manage.py runserver` | http://127.0.0.1:8000/api/docs/ |
| 2 | `npm run dev` (customer-web) | http://localhost:5173 |
| 3 | `npm run dev` (admin-dashboard) | http://localhost:5174 |

---

## Signing in as a shopper

There is **no password** for customers and no signup form. The flow is:

1. Add items to the cart as a guest (no login needed).
2. Click **Login**, enter any 10-digit mobile number, then **Send code**.
3. A 6-digit OTP comes back in the `send-otp/` API response as `dev_otp` — read
   it in devtools (**F12 → Network → `send-otp/` → Response**). No SMS is sent.
4. Enter it — the account is created automatically if the number is new.

Your guest cart is merged into the account on the first request after the
session is confirmed, so items added before signing in survive the login.

The four seeded customers (`+919876500001` … `+919876500004`) already have
order history, so signing in with one of those numbers shows a populated
account.

### OTP rate limits will stop you while testing

The defaults are tight, by design:

| Limit | Default |
|---|---|
| Resend cooldown | 60 seconds |
| Codes per account per hour | 5 |
| Codes per IP per hour | 20 |

If you sign in and out a few times you will hit `otp_throttled` — this is not a
bug. Either wait, or raise the limits in `backend/.env` for local work:

```ini
OTP_RESEND_COOLDOWN_SECONDS=0
OTP_MAX_REQUESTS_PER_HOUR=1000
OTP_MAX_REQUESTS_PER_IP_PER_HOUR=1000
```

Restart `runserver` after editing `.env`. To clear the counters immediately
without restarting, run this from `backend/`:

```bash
python manage.py shell -c "from apps.authentication.models import OTPThrottle, OTPVerification; OTPThrottle.objects.all().delete(); OTPVerification.objects.all().delete(); print('throttle cleared')"
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `connection to server at "127.0.0.1", port 5432 failed` | PostgreSQL is not running — step 2. |
| `password authentication failed for user "ums_mart_user"` | Password in `backend/.env` does not match step 3. Fix with `ALTER ROLE ums_mart_user WITH PASSWORD '1234';` |
| `FATAL: database "ums_mart_db" does not exist` | Step 3 did not complete. Re-run `CREATE DATABASE`. |
| `permission denied for schema public` (during `migrate`) | The role does not own the database — normal on PostgreSQL 15+. See [If the database already exists](#if-the-database-already-exists). Quick fix: `ALTER DATABASE ums_mart_db OWNER TO ums_mart_user;` |
| `MigrationSchemaMissing: Unable to create the django_migrations table` | Same cause as the row above, same fix. |
| `ModuleNotFoundError: No module named 'django'` | Venv not activated, or `pip install` ran from the wrong folder. |
| `ModuleNotFoundError: No module named 'requests'` (or `'argon2'`) | Your `requirements.txt` is from an older zip — two dependencies were missing from it. Re-copy `backend/requirements.txt` and run `pip install -r backend/requirements.txt` again. |
| `manage.py check` fails while importing `urls_admin` | Same cause as above: a missing third-party module surfacing through the URL import chain. Read the **last** line of the traceback — it names the module. |
| `Python was not found; run without arguments to install from the Microsoft Store` | Python is not installed, or not on PATH. Use `py` instead, or see [Windows: getting `python` to work](#windows-getting-python-to-work). |
| `'python' is not recognized` (Windows) | Python is not on PATH. Use `py`, or reinstall with "Add Python to PATH" ticked. |
| `py` prints "No suitable Python runtime found" | No Python 3.11+ installed. Get it from python.org. |
| Port 8000 already in use | `python manage.py runserver 8001`, then change the proxy `target` in **both** `frontend/*/vite.config.js`. |
| Port 5173 in use | Vite moves to 5174/5175 automatically — but that collides with the admin console. Stop the stray process instead. |
| Frontend loads, every list is empty | The API (terminal 1) is not running. |
| Product images broken | `seed_data` did not create them. Re-run it from `backend/`. |
| Login "works" but you are signed out on refresh | Cookies are being dropped. Check you are on `http://localhost:5173` (not a proxied host) and that `COOKIE_CROSS_SITE` is **not** set. |
| `psql: command not found` (macOS) | `brew install postgresql@17`, then add its `bin` to PATH. |

---

## Optional: run the test suites

With the API still running:

```bash
# Django unit tests — uses a throwaway test database
cd backend && python manage.py test

# real HTTP smoke test, from the repo root
python run_smoke.py

# front-end contract suite, needs the API running
cd frontend && python frontend_e2e.py
```

> `manage.py test` runs against `test_ums_mart_db`, a separate database, so it
> does **not** touch your demo data. (In this sandbox it did once — that is an
> artefact of the sandbox, not of the command. If your seeded data ever
> disappears, `python manage.py seed_data` restores it in seconds.)

---

## What changed since RUN.md

`RUN.md` is kept for history. These three statements in it are wrong for the
current build:

| RUN.md says | Reality |
|---|---|
| "Authentication: **None.**" | Customer OTP login and a separate admin login are fully wired, on Django sessions with HttpOnly cookies. |
| "The storefront header lets you pick which demo shopper you are." | That switcher is gone. Sign in with a mobile number; the account is created on first use. |
| "Open http://localhost:5174" without setup | The admin console needs an account: `python manage.py create_admin`. |

Also note `RUN.md` omits `create_admin` entirely, so following it leaves you
unable to log into the admin console.
