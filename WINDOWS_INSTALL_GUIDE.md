# UMS Mart on Windows: database to mobile app

Follow the stages in order. Every command is for **PowerShell**.
Do the check at the end of a stage before starting the next one.

Project folder used below: `C:\ums_mart`

---

## Stage 0: Unzip

Unzip into a **new** folder. Do not unzip over your old `ums_mart` folder: the
old mobile `android` files would mix with the new ones and break the build.

```powershell
Expand-Archive -Path "$env:USERPROFILE\Downloads\ums_mart_windows_ready.zip" -DestinationPath C:\
```

Check: `C:\ums_mart` now contains `backend`, `frontend` and `mobile`.

---

## Stage 1: Install the tools

Skip any tool whose check already prints a version.

| Tool | Get it from | Check |
|---|---|---|
| PostgreSQL 14 or newer | https://www.postgresql.org/download/windows/ | "SQL Shell (psql)" is in the Start menu |
| Python 3.11 or newer | https://www.python.org/downloads/ (tick **Add Python to PATH**) | `py --version` |
| Node.js 20 or newer | https://nodejs.org/ | `node --version` |
| Git for Windows | https://git-scm.com/downloads/win | `git --version` |
| Flutter SDK 3.50 | see below | `flutter --version` |
| Android Studio | https://developer.android.com/studio | see below |

Remember the password you give the `postgres` user during the PostgreSQL install.

### Flutter SDK

1. Download https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.50.0-stable.zip
2. Extract it and add it to your PATH:

```powershell
Expand-Archive -Path "$env:USERPROFILE\Downloads\flutter_windows_3.50.0-stable.zip" -DestinationPath "$env:USERPROFILE\develop"
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";$env:USERPROFILE\develop\flutter\bin", "User")
```

3. **Close PowerShell and open a new window**, then run `flutter --version`.

### Android Studio

1. Install it and finish the first-run wizard (it downloads the Android SDK).
2. Welcome screen → **More Actions → SDK Manager → SDK Tools** tab → tick
   **Android SDK Command-line Tools (latest)** → **Apply**.
3. Accept the licences (answer `y` to each):

```powershell
flutter doctor --android-licenses
```

4. Welcome screen → **More Actions → Virtual Device Manager → Create Device** →
   pick a Pixel phone → pick the recommended system image → **Finish**.

Check:

```powershell
flutter doctor
```

The **Flutter** and **Android toolchain** lines must have a green tick. Other
lines (Chrome, Visual Studio) do not matter for this project.

---

## Stage 2: Create the database

Open **SQL Shell (psql)** from the Start menu. Press Enter at each prompt, then
type your `postgres` password. Paste:

```sql
CREATE ROLE ums_mart_useradminums WITH LOGIN PASSWORD '1234' CREATEDB;
CREATE DATABASE ums_mart_databaseadmin OWNER ums_mart_useradminums;
ALTER DATABASE ums_mart_databaseadmin OWNER TO ums_mart_useradminums;
\c ums_mart_databaseadmin
GRANT ALL ON SCHEMA public TO ums_mart_useradminums;
\q
```

"already exists" on the first two lines is fine: it means you created them before.
You never create tables by hand. Stage 3 does that.

---

## Stage 3: Start the API (window 1)

The zip already contains `backend\.env` with the database name, user and
password from Stage 2.

```powershell
cd C:\ums_mart
py -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\venv\Scripts\python.exe backend\manage.py migrate
.\venv\Scripts\python.exe backend\manage.py seed_data --flush
.\venv\Scripts\python.exe backend\manage.py create_admin --username admin --email admin@example.com --password "UMSMart@Admin2026"
.\venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000
```

- `seed_data --flush` **deletes existing shop data** and loads the demo data.
  Skip that line if your database already has data you want to keep.
- If `create_admin` says an admin already exists, run the same line with
  `--rotate` added at the end.

Leave this window open.

Check: open http://127.0.0.1:8000/health/ and look for `"database": "up"`.

---

### Real pictures (run once, after the demo data is loaded)

The demo data has only colour tiles as pictures. This loads the real pictures
from the `pictures` folder, so the store, the admin panel and the mobile app
all show them:

```powershell
cd C:\ums_mart\backend
C:\ums_mart\venv\Scripts\python.exe ..\pictures\load_pictures.py
```

On a fresh install it must end with `Products : 66 updated`,
`Categories : 26 updated`, `Banners : 3 updated`. Run it again every time you run `seed_data --flush`,
because that command puts the colour tiles back. A picture you uploaded in the
admin panel is kept.

## Stage 4: Start the two web apps (windows 2 and 3)

Window 2, storefront:

```powershell
cd C:\ums_mart\frontend\customer-web
npm install
npm run dev
```

Window 3, admin dashboard:

```powershell
cd C:\ums_mart\frontend\admin-dashboard
npm install
npm run dev
```

Check:

| App | Open | Login |
|---|---|---|
| Storefront | http://127.0.0.1:5173 | mobile `+919876500001`, the OTP is shown on screen |
| Admin | http://localhost:5174 | `admin` / `UMSMart@Admin2026`, then the OTP shown on screen |

Use exactly these two addresses. `127.0.0.1` for the storefront and `localhost`
for the admin keeps the two logins from overwriting each other.

---

## Stage 5: Run the mobile app (window 4)

1. Start the emulator: Android Studio → **Virtual Device Manager** → press the
   **Play** button. Wait for the phone home screen.
2. The API from Stage 3 must still be running.
3. Run the app:

```powershell
cd C:\ums_mart\mobile\ums_mart_customer
flutter pub get
flutter run
```

The first build takes several minutes. Later builds are much faster.

Check: the UMS Mart home screen shows products. Tap **Profile**, log in with
`+919876500002`, and use the "Dev OTP" code shown on the login screen.

### On a real phone instead of the emulator

1. Phone and PC on the same Wi-Fi. On the phone, turn on **Developer options →
   USB debugging** and connect the USB cable.
2. Find your PC's address:

```powershell
ipconfig | findstr IPv4
```

3. Open `C:\ums_mart\backend\.env`, add that address to the end of the
   `ALLOWED_HOSTS` line (comma, no spaces), save, and **restart the API**.
4. Allow the phone through the firewall (PowerShell **as Administrator**, once):

```powershell
New-NetFirewallRule -DisplayName "UMS Dev" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

5. Run with your PC's address in place of `192.168.1.38`:

```powershell
flutter run --dart-define=API_BASE=http://192.168.1.38:8000
```

---

## Every day after the first time

| Window | Command |
|---|---|
| 1 | `cd C:\ums_mart` then `.\venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000` |
| 2 | `cd C:\ums_mart\frontend\customer-web` then `npm run dev` |
| 3 | `cd C:\ums_mart\frontend\admin-dashboard` then `npm run dev` |
| 4 | start the emulator, `cd C:\ums_mart\mobile\ums_mart_customer` then `flutter run` |

---

## If something goes wrong

| What you see | Fix |
|---|---|
| `flutter` is not recognized | Open a new PowerShell window after the PATH step in Stage 1. |
| `flutter doctor`: "cmdline-tools component is missing" | Stage 1, Android Studio step 2. |
| `password authentication failed` | The name or password in `backend\.env` does not match Stage 2. |
| `database ... does not exist` | Run the `CREATE DATABASE` line from Stage 2. |
| `py` is not recognized | Reinstall Python with **Add Python to PATH** ticked. |
| "running scripts is disabled" for `npm` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. |
| Mobile app opens but shows no products | The API is not running, or was started without `0.0.0.0:8000`. Restart it as in Stage 3. |
| Real phone cannot connect | Recheck steps 3 and 4 of the real-phone section, and that both are on the same Wi-Fi. |
| "Too many verification requests" | Wait a few minutes, or in psql run `DELETE FROM auth_otp_throttle;` |
| `.env` change has no effect | `.env` is read only when the API starts. Restart it. |
| Emulator will not start | Turn on virtualization in the PC's BIOS, then retry. |
| Admin save fails with a security token error | You opened the admin by IP address. Use http://localhost:5174. |
| Port already in use | `netstat -ano \| findstr :8000`, then `taskkill /PID <number> /F`. |
