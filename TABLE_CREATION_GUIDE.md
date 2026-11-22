# UMS Mart — Table Creation Guide (PostgreSQL)

**Your names (use these exactly, both in SQL and in `backend\.env`):**

| | |
|---|---|
| Database | `ums_mart_databaseadmin` |
| Role / user | `ums_mart_useradminums` |
| Password | `1234` |
| Host / port | `127.0.0.1` / `5432` |

**You never write `CREATE TABLE` by hand.** Django's migrations create all 39 tables. You only create the *database and the role*.

---

## Step 1 — Create the role + database (copy-paste into psql)

Open: **Start menu → "SQL Shell (psql)"** → Enter through all prompts (Server: `localhost`, Database: `postgres`, Port: `5432`, Username: `postgres`, Password: the one you set when installing PostgreSQL).

```sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ums_mart_useradminums') THEN
    CREATE ROLE ums_mart_useradminums WITH LOGIN PASSWORD '1234' CREATEDB;
  ELSE
    ALTER ROLE ums_mart_useradminums WITH LOGIN PASSWORD '1234' CREATEDB;
  END IF;
END
$$;
```

Then, **only if the database does not exist yet** (check with `\l`):

```sql
CREATE DATABASE ums_mart_databaseadmin OWNER ums_mart_useradminums;
```

Always run this after — it fixes `permission denied for schema public` on PostgreSQL 15+:

```sql
ALTER DATABASE ums_mart_databaseadmin OWNER TO ums_mart_useradminums;
```

Reconnect **as the owner** and grant the schema:

```sql
\c ums_mart_databaseadmin ums_mart_useradminums
```
(enter password `1234`)

```sql
GRANT ALL ON SCHEMA public TO ums_mart_useradminums;
```

> `CREATEDB` is **not optional** — the test suite builds its own temporary database.

---

## Step 2 — Verify you can create tables

Still in the same psql window, as `ums_mart_useradminums` on `ums_mart_databaseadmin`:

```sql
CREATE TABLE _probe(x int);
DROP TABLE _probe;
```

No error = fine. `ERROR: permission denied for schema public` = re-run the `ALTER DATABASE ... OWNER` + `GRANT` lines above.

`\q` to quit.

---

## Step 3 — Point the project at the database

File: `backend\.env` (create it by copying `backend\.env.example` if missing). The lines that matter:

```ini
DB_NAME=ums_mart_databaseadmin
DB_USER=ums_mart_useradminums
DB_PASSWORD=1234
DB_HOST=127.0.0.1
DB_PORT=5432
```

Rules:
- **`DB_PASSWORD` has no default** — empty/missing ⇒ "password authentication failed".
- **Delete any `DATABASE_URL` line** — it overrides every `DB_*` value.
- No quotes around values, no spaces around `=`.

---

## Step 4 — Create the tables

```powershell
cd C:\Users\user\Desktop\mono\ums_mart
.\venv\Scripts\Activate.ps1
cd backend
python manage.py migrate
```

> **PowerShell needs the leading `.\`** — `venv\Scripts\activate` alone gives
> *"ObjectNotFound: venv\Scripts\activate: CommandNotFoundException"*, because
> PowerShell does not run a relative executable/path without it.
>
> **If PowerShell still refuses** (*"running scripts is disabled on this system"*):
>
> ```powershell
> Set-ExecutionPolicy -Scope Process -Bypass
> .\venv\Scripts\Activate.ps1
> ```
>
> **Or skip activation entirely** and call the venv's python directly — one
> command, no policy issues, works in cmd and PowerShell alike:
>
> ```powershell
> .\venv\Scripts\python.exe backend\manage.py migrate
> ```

Expected: ~40 lines of `Applying catalog.0001_initial... OK`, ending with nothing red.

Check the tables landed (same window — `python` works once the venv is active;
otherwise prefix every command with `.\venv\Scripts\python.exe` from the repo root):

```powershell
python manage.py showmigrations
```
Everything must show `[X]`.

In psql (`\c ums_mart_databaseadmin ums_mart_useradminums` then `\dt`) you should see **39** tables.

---

## Step 5 — Fill them

```powershell
python manage.py seed_data --flush
python manage.py create_admin --username admin --email admin@example.com --password "UMSMart@Admin2026"
```

`--flush` empties demo rows first; safe to repeat. If `create_admin` says *"An admin account already exists"*, add `--rotate` to reset that admin's password.

---

## The 39 tables Django creates

| # | Table | App | Purpose |
|---|---|---|---|
| 1 | `accounts_user` | accounts | Login account: username, mobile, email, role, password |
| 2 | `accounts_customer_profile` | accounts | 1-to-1 link account ↔ customer |
| 3 | `addresses_address` | addresses | Delivery addresses |
| 4 | `auth_otp_throttle` | authentication | OTP rate-limit counters |
| 5 | `auth_password_reset` | authentication | Password reset tokens |
| 6 | `auth_otp_verification` | authentication | Issued OTPs (hashed) |
| 7 | `auth_user_session` | authentication | Device/session audit rows |
| 8 | `banners_banner` | banners | Home carousel banners |
| 9 | `cart_cart` | cart | Carts (guest via `uid`, or customer) |
| 10 | `cart_item` | cart | Cart lines with price snapshot |
| 11 | `catalog_category` | catalog | Category tree (`parent` self-FK) |
| 12 | `catalog_product` | catalog | Products |
| 13 | `catalog_product_image` | catalog | Extra product gallery images |
| 14 | `customers_customer` | customers | Shopper record (mobile-keyed) |
| 15 | `customers_customer_note` | customers | Admin notes on a shopper |
| 16 | `inventory_stock` | inventory | Quantity on hand per product |
| 17 | `inventory_log` | inventory | Every stock movement |
| 18 | `orders_order` | orders | Orders + delivery address snapshot |
| 19 | `orders_order_item` | orders | Order lines (name/SKU snapshot) |
| 20 | `orders_status_history` | orders | Status transitions |
| 21 | `payments_payment` | payments | COD / UPI payment records |
| 22 | `payments_verification` | payments | Payment approval trail |
| 23 | `payments_refund` | payments | Refunds |
| 24 | `promotions_promotion` | promotions | Coupons / discounts |
| 25 | `promotions_redemption` | promotions | Who used which coupon |
| 26 | `store_settings_holiday` | store_settings | Closed dates |
| 27 | `store_settings_delivery_slab` | store_settings | Delivery charge tiers |
| 28 | `store_settings_store` | store_settings | Single store config row |
| 29 | `wishlist_wishlist` | wishlist | A shopper's wishlist |
| 30 | `wishlist_item` | wishlist | Wishlist lines |

Plus **9 Django framework tables** (do not touch):

`django_migrations`, `django_content_type`, `django_session`, `django_admin_log`,
`auth_permission`, `auth_group`, `auth_group_permissions`,
`auth_user_groups`, `auth_user_user_permissions`

**30 + 9 = 39 tables.**

> `auth_user` is *not* one of them — this project's user table is `accounts_user`.
> Querying `auth_user` returns "relation does not exist" / zero rows, by design.

---

## Working rules (why the schema looks like this)

1. **Never `CREATE TABLE` manually.** If a table is missing, the fix is `python manage.py migrate`, never SQL. Half hand-made tables are how the seeder starts failing on FK errors.
2. **Do not edit migration files.** To change a table, edit `models.py`, then `makemigrations` → `migrate`.
3. **Every table has `id` BigAutoField + `uid` UUID + `created_at`/`updated_at`.** The `uid` is what APIs expose; the integer `id` is internal.
4. **Soft delete:** `catalog_product`, `customers_customer` use `is_deleted` + `deleted_at`. A "deleted" row is still in the table — filter with `is_deleted=False`.
5. **Not every model is a table.** `BaseModel` is `abstract=True`, so it appears in no table; `store_settings_store` is a singleton config row, not a per-store table.

---

## Troubleshooting cheat-sheet

| Error | Cause | Fix |
|---|---|---|
| `permission denied for schema public` | Role doesn't own the DB (PG15+) | `ALTER DATABASE ums_mart_databaseadmin OWNER TO ums_mart_useradminums;` then `GRANT ALL ON SCHEMA public TO ums_mart_useradminums;` |
| `database "ums_mart_databaseadmin" does not exist` | Step 1 skipped | Run `CREATE DATABASE ...` |
| `password authentication failed for user` | `DB_PASSWORD` missing or mismatched | Fix `backend\.env`, or `ALTER ROLE ums_mart_useradminums WITH PASSWORD '1234';` |
| `role ... does not exist` | Role not created | Re-run the `DO $$ ... $$;` block |
| `relation "auth_user" does not exist` | Wrong table | Use `accounts_user` |
| Credentials look ignored | `DATABASE_URL` set | Delete that line from `.env` |
| `no such table` after migrate | Pointed at SQLite / wrong DB | Check `DB_NAME` and that `DJANGO_SETTINGS_MODULE=config.settings.development` |
| Tests fail creating test DB | Role lacks `CREATEDB` | `ALTER ROLE ums_mart_useradminums CREATEDB;` |
