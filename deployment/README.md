# UMS Mart — Deployment Guide (Hostinger VPS)

This folder contains **everything** needed to run the UMS Mart API on a fresh
Ubuntu/Debian VPS. Nothing here is imported by the Django application, so the
hosting configuration can change without touching business logic.

```
deployment/
├── README.md                      ← you are here
├── gunicorn/
│   └── gunicorn.conf.py           Gunicorn processes, socket, logging
├── nginx/
│   └── ums_mart.conf              TLS termination, reverse proxy, static/media
└── scripts/
    ├── deploy.sh                  idempotent deploy / update
    ├── backup.sh                  pg_dump + checksum + retention
    ├── ums-mart.service           systemd unit for Gunicorn
    └── smoke_test.py              118-check end-to-end API suite
```

> **Assumed starting point:** a fresh VPS with root SSH access. Nothing is
> pre-configured — every command below is meant to be run in order.

---

## 0. What you need before starting

| Item | Notes |
|---|---|
| VPS | Hostinger KVM 2 or larger (2 vCPU / 2 GB RAM minimum) |
| OS | Ubuntu 22.04 / 24.04 or Debian 12 |
| Domain | e.g. `api.umsmart.com`, with an **A record** → VPS IPv4 |
| SSH key | Password logins get disabled in step 11 |

Throughout, replace `api.umsmart.com` with your own domain and
`203.0.113.10` with your VPS IP.

---

## 1. Server basics

```bash
ssh root@203.0.113.10

apt update && apt upgrade -y
apt install -y build-essential git curl ufw fail2ban \
               nginx postgresql postgresql-contrib \
               python3 python3-venv python3-dev libpq-dev \
               certbot python3-certbot-nginx
```

Set the timezone and confirm it matches `TIME_ZONE` in `.env`:

```bash
timedatectl set-timezone Asia/Kolkata
timedatectl status
```

---

## 2. Create the service user

The application must **not** run as root.

```bash
adduser --system --group --home /home/ums_mart --shell /bin/bash umsmart
usermod -aG www-data umsmart

mkdir -p /home/ums_mart
chown -R umsmart:umsmart /home/ums_mart
```

---

## 3. PostgreSQL in production

### 3.1 Create the role and database

```bash
sudo -u postgres psql
```

```sql
-- A dedicated least-privilege role. Replace the password.
CREATE ROLE ums_mart_user WITH LOGIN PASSWORD 'GENERATE_A_LONG_RANDOM_PASSWORD';
CREATE DATABASE ums_mart_db OWNER ums_mart_user ENCODING 'UTF8'
    LC_COLLATE='en_US.UTF-8' LC_CTYPE='en_US.UTF-8' TEMPLATE=template0;

-- Nothing outside the app needs to connect.
REVOKE ALL ON DATABASE ums_mart_db FROM PUBLIC;
GRANT ALL PRIVILEGES ON DATABASE ums_mart_db TO ums_mart_user;

-- The app creates tables during migrations, so it needs schema ownership.
\c ums_mart_db
GRANT ALL ON SCHEMA public TO ums_mart_user;
ALTER SCHEMA public OWNER TO ums_mart_user;
```

Generate the password with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.2 Bind PostgreSQL to localhost only

Django and PostgreSQL are on the same machine, so the database must never be
reachable from the internet.

```bash
# /etc/postgresql/*/main/postgresql.conf
listen_addresses = 'localhost'
ssl = on

# /etc/postgresql/*/main/pg_hba.conf  — only these lines for the app user
host    ums_mart_db    ums_mart_user    127.0.0.1/32    scram-sha-256
host    ums_mart_db    ums_mart_user    ::1/128         scram-sha-256
```

```bash
systemctl restart postgresql
systemctl enable postgresql
```

Verify from outside — this **must** time out or be refused:

```bash
# from your laptop
nc -zv 203.0.113.10 5432     # expected: connection refused / timeout
```

### 3.3 Tuning for a small VPS (2 GB)

In `postgresql.conf`, a sane starting point:

```conf
shared_buffers = 256MB
effective_cache_size = 768MB
work_mem = 8MB
maintenance_work_mem = 64MB
max_connections = 60
wal_compression = on
```

Restart PostgreSQL after changing these.

---

## 4. Deploy the code

```bash
sudo -u umsmart -H bash
cd /home/ums_mart

# Option A - git
git clone <YOUR_REPO_URL> .

# Option B - upload the project ZIP from your machine
#   scp ums_mart.zip umsmart@203.0.113.10:/home/ums_mart/
#   unzip ums_mart.zip && mv ums_mart/* . && rmdir ums_mart
```

Expected layout after this step:

```
/home/ums_mart/
├── backend/
├── deployment/
├── docs/
├── .env.example
└── README.md
```

### 4.1 Virtualenv

```bash
python3 -m venv /home/ums_mart/venv
/home/ums_mart/venv/bin/pip install --upgrade pip
/home/ums_mart/venv/bin/pip install -r /home/ums_mart/backend/requirements.txt
```

### 4.2 Environment file

```bash
cd /home/ums_mart
cp .env.example backend/.env
chmod 640 backend/.env
nano backend/.env
```

Minimum values to change:

```ini
DJANGO_SETTINGS_MODULE=config.settings.production
DEBUG=False
DJANGO_SECRET_KEY=<64-char random string>
DJANGO_ALLOWED_HOSTS=api.umsmart.com,203.0.113.10

DB_NAME=ums_mart_db
DB_USER=ums_mart_user
DB_PASSWORD=<the password from step 3.1>
DB_HOST=127.0.0.1
DB_PORT=5432
DB_CONN_MAX_AGE=60

STATIC_ROOT=/home/ums_mart/backend/staticfiles
MEDIA_ROOT=/home/ums_mart/backend/media
LOG_DIR=/home/ums_mart/backend/logs

CORS_ALLOWED_ORIGINS=https://admin.umsmart.com
CSRF_TRUSTED_ORIGINS=https://api.umsmart.com
ADMIN_EMAIL=admin@umsmart.com
```

Generate the secret key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

> The app **refuses to start** with production settings if `DJANGO_SECRET_KEY`
> is missing, shorter than 50 characters, or still the development placeholder.
> That check is intentional.

### 4.3 Migrate and seed

```bash
cd /home/ums_mart/backend
source /home/ums_mart/venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.production

python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput

# Optional demo data (categories, products, customers, coupons, banners)
python manage.py seed_data

# Admin login for the Django admin (there is no customer auth in this phase)
python manage.py createsuperuser
```

### 4.4 Directories the app writes to

```bash
mkdir -p /home/ums_mart/backend/{media,staticfiles,logs}
chown -R umsmart:www-data /home/ums_mart/backend/media
chown -R umsmart:umsmart  /home/ums_mart/backend/logs
chmod -R 775 /home/ums_mart/backend/media
```

---

## 5. Gunicorn (systemd)

```bash
sudo cp /home/ums_mart/deployment/scripts/ums-mart.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ums-mart
sudo systemctl status ums-mart
```

The unit binds Gunicorn to a **UNIX socket** at
`/run/gunicorn/ums_mart.sock`, so the app server is unreachable from the
internet and Nginx is the only client.

```bash
# Watch the log while it boots
journalctl -u ums-mart -f

# Confirm the socket exists
ls -l /run/gunicorn/ums_mart.sock
```

The worker count comes from `gunicorn.conf.py` (default `2 × cores + 1`).
Override without editing the file:

```bash
sudo systemctl edit ums-mart
# [Service]
# Environment="GUNICORN_WORKERS=3"
```

---

## 6. Nginx

```bash
sudo cp /home/ums_mart/deployment/nginx/ums_mart.conf /etc/nginx/sites-available/ums_mart
sudo sed -i 's/api.umsmart.com/YOUR_DOMAIN/g' /etc/nginx/sites-available/ums_mart
sudo ln -sf /etc/nginx/sites-available/ums_mart /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
sudo systemctl reload nginx
```

Nginx handles:

| Path | Served by |
|---|---|
| `/static/*` | directly from `staticfiles/` (30-day cache) |
| `/media/*` | directly from `media/` (7-day cache) |
| `/health/` | proxied to Gunicorn, rate-limit free |
| everything else | proxied to Gunicorn over the UNIX socket |

After `nginx -t` passes but before TLS is configured, the site returns a 502
until step 7 — that is expected.

---

## 7. HTTPS (Let's Encrypt)

```bash
sudo certbot --nginx -d api.umsmart.com --redirect --agree-tos -m admin@umsmart.com
```

certbot rewrites the `server_name`, inserts the certificate paths and sets up
the renewal timer. Verify:

```bash
sudo certbot renew --dry-run
systemctl list-timers | grep certbot
curl -s https://api.umsmart.com/health/
```

Expected:

```json
{"status": "ok", "service": "ums-mart-api", "version": "1.0.0", "database": "up"}
```

> **HSTS:** `SECURE_HSTS_PRELOAD` defaults to `False` on purpose — browser
> preload lists are effectively permanent. Only enable it once every subdomain
> is HTTPS-only.

---

## 8. Firewall and intrusion prevention

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
ufw status verbose
```

Port 5432 must **not** appear in that list. Confirm:

```bash
ss -tlnp | grep -E '5432|8000|8001'
# 5432 should show 127.0.0.1:5432 only
```

Basic SSH hardening (`/etc/ssh/sshd_config`):

```conf
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
```

```bash
# Test your key login in a second terminal BEFORE closing this one.
systemctl restart ssh
```

`fail2ban` ships with a working `sshd` jail:

```bash
systemctl enable --now fail2ban
fail2ban-client status sshd
```

---

## 9. Security checklist before going live

- [ ] `DEBUG=False` in `backend/.env`
- [ ] `DJANGO_SECRET_KEY` is unique and ≥ 50 characters
- [ ] `.env` is `640`, owned by `umsmart`, and **not** in git
- [ ] `python manage.py check --deploy` is clean
- [ ] PostgreSQL listens on `127.0.0.1` only
- [ ] Firewall allows only 22/80/443
- [ ] HTTPS works and HTTP redirects to it
- [ ] SSH password login disabled
- [ ] Admin password is strong; `createsuperuser` was run
- [ ] `/api/docs/` and `/admin/` are **not** publicly reachable (see §10)
- [ ] Backups run (§12) and a restore has been rehearsed

### 10. Locking down the API — **read this before exposing the server**

**This phase has no authentication.** Every endpoint is open, including admin
CRUD on products, orders, payments and store settings. Anyone who finds the
domain can read customer data and approve payments.

Until the authentication phase ships, pick one:

1. **IP allow-list** — put the API behind the office/static IP:

   ```nginx
   location / {
       allow 203.0.113.0/24;
       deny all;
       proxy_pass http://ums_mart_api;
   }
   ```

2. **Basic auth in front of everything** — crude but effective:

   ```bash
   sudo apt install apache2-utils
   sudo htpasswd -c /etc/nginx/.htpasswd demo
   ```

   ```nginx
   location / {
       auth_basic "UMS Mart staging";
       auth_basic_user_file /etc/nginx/.htpasswd;
       proxy_pass http://ums_mart_api;
   }
   ```

3. **Do not expose it at all** — keep Nginx bound to localhost and reach it
   through an SSH tunnel while you integrate the front-end.

Also keep the docs and admin off the public internet:

```nginx
location ~ ^/(admin|api/docs|api/redoc|api/schema) {
    allow 203.0.113.0/24;   # your IP
    deny all;
    proxy_pass http://ums_mart_api;
}
```

`/media/` contains **payment screenshots**. Either restrict that location the
same way or move uploads to object storage with signed URLs.

---

## 11. Ongoing operations

### Deploy an update

```bash
sudo -u umsmart -u umsmart bash /home/ums_mart/deployment/scripts/deploy.sh
```

The script pulls, installs, checks, **backs up**, migrates, collects static,
restarts Gunicorn, reloads Nginx and verifies `/health/`. If any step fails it
stops and leaves the previous release running.

Flags: `--no-pull` (deploy code already on disk), `--help`.

### Manual service commands

```bash
sudo systemctl restart ums-mart
sudo systemctl status ums-mart
journalctl -u ums-mart -n 200 --no-pager
sudo tail -f /home/ums_mart/backend/logs/*.log
sudo tail -f /var/log/nginx/ums_mart_error.log
```

### Migrations

```bash
cd /home/ums_mart/backend
source /home/ums_mart/venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.production

python manage.py migrate --plan     # review BEFORE applying
python manage.py migrate
```

Always back up first (`deployment/scripts/backup.sh`). `deploy.sh` does this
automatically.

### Run the smoke suite on the server

```bash
cd /home/ums_mart
source venv/bin/activate
DJANGO_SETTINGS_MODULE=config.settings.production python run_smoke.py
```

---

## 12. Backups

```bash
sudo -u umsmart bash /home/ums_mart/deployment/scripts/backup.sh
```

Produces `ums_mart_<timestamp>.dump` (compressed `pg_dump -Fc`), a `.sha256`
checksum and a `.log`. Every archive is verified with `pg_restore --list`
before the script reports success.

Schedule it:

```bash
sudo crontab -u umsmart -e
```

```cron
# Database backup, 02:15 every day, keep 14 days
15 2 * * * /bin/bash /home/ums_mart/deployment/scripts/backup.sh --keep 14 >> /var/log/ums_mart_backup.log 2>&1
```

**Copy backups off the VPS** — a backup on the same disk does not survive disk
failure. `rclone` to any object store is the simplest option:

```cron
30 2 * * * rclone sync /home/ums_mart/backups remote:ums-mart-backups --max-age 30d
```

### Restore

```bash
# 1. Stop the app so nothing writes during the restore
sudo systemctl stop ums-mart

# 2. Recreate an empty database
sudo -u postgres psql -c "DROP DATABASE ums_mart_db;"
sudo -u postgres psql -c "CREATE DATABASE ums_mart_db OWNER ums_mart_user;"

# 3. Restore
PGPASSWORD='<DB_PASSWORD>' pg_restore \
    --host=127.0.0.1 --username=ums_mart_user --dbname=ums_mart_db \
    --no-owner --no-privileges \
    /home/ums_mart/backups/ums_mart_20260101T021500Z.dump

# 4. Restart and verify
sudo systemctl start ums-mart
curl -s https://api.umsmart.com/health/
```

Rehearse a restore on a scratch database at least once before you need one.

---

## 13. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `502 Bad Gateway` | Gunicorn down or socket missing | `systemctl status ums-mart`; `journalctl -u ums-mart -n 100` |
| `400 Bad Request` (Django HTML) | Host not in `DJANGO_ALLOWED_HOSTS` | add the domain to `.env`, restart |
| `DisallowedHost` in logs | same | same |
| `ImproperlyConfigured: DJANGO_SECRET_KEY...` | secret missing/short/placeholder | set a 50+ char key in `.env` |
| Static files 404 | `collectstatic` not run, or `STATIC_ROOT` mismatch | run `collectstatic`; compare with `alias` in Nginx |
| Uploads 403 | `media/` not writable by `umsmart` | `chown -R umsmart:www-data backend/media` |
| Infinite redirect loop | `SECURE_SSL_REDIRECT` on but Nginx not sending `X-Forwarded-Proto` | keep `proxy_set_header X-Forwarded-Proto $scheme;` |
| `permission denied` on the socket | Nginx (www-data) cannot read `/run/gunicorn` | `usermod -aG www-data umsmart`; `systemctl restart ums-mart nginx` |
| Migrations hang | waiting on a table lock | `select * from pg_stat_activity;` find the blocking PID |
| Certbot fails | DNS not propagated or port 80 closed | `dig +short api.umsmart.com`; `ufw allow 'Nginx Full'` |

---

## 14. Verified on this release

The following were **actually executed** while preparing this project, on
PostgreSQL 17.11 + Gunicorn 26.2 + Nginx 1.26:

- `manage.py check` and `manage.py check --deploy` → 0 issues
- `manage.py migrate` → all 13 migrations applied to a real PostgreSQL database
- 371 Django tests → all passing
- 118-check end-to-end smoke suite → 118 passed, 0 failed
- Gunicorn serving the WSGI app on a UNIX socket behind Nginx, HTTP→HTTPS
  redirect, TLS, security headers, `/health/`, `/api/v1/`, `/api/docs/`,
  `/api/schema/`, `/admin/` all responding correctly
- `backup.sh` → real 221 KB dump, verified with `pg_restore --list`, then
  restored into a scratch database and row counts confirmed

**Not** executed: an actual Hostinger VPS provision, DNS, Let's Encrypt
issuance and systemd startup. Those steps above are instructions, not claims of
having been run in this environment.
