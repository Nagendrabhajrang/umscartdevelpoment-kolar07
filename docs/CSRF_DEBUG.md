# Diagnosing "Your security token expired" in 60 seconds

Run this **in the storefront page** (not the admin page), with the store open at the
address you normally use. Open DevTools (`F12`) → **Console** → paste → Enter.

```js
(async () => {
  const api = "/api/v1";
  const out = { page: location.href, host: location.host, secure: location.protocol };
  out.csrfCookie = (document.cookie.split("; ").find(c => c.startsWith("ums_mart_csrftoken")) || "(missing)");
  out.cookies = document.cookie.split("; ").map(c => c.split("=")[0]).filter(Boolean);
  out.storage = { bearer: localStorage.getItem("ums.auth.bearer") ? "present" : "none" };

  // 1. what does the CSRF endpoint answer, and does it set a cookie we can read?
  const before = out.csrfCookie;
  const csrf = await fetch("/api/auth/csrf/", { credentials: "include", cache: "no-store" });
  out.csrfEndpoint = { status: csrf.status, setCookie: csrf.headers.get("set-cookie") };
  out.csrfCookieAfter = (document.cookie.split("; ").find(c => c.startsWith("ums_mart_csrftoken")) || "(still missing)");
  out.cookieWasReplaced = before !== out.csrfCookieAfter;

  // 2. is a session even present? (401 = guest, 200 = signed in)
  const sess = await fetch("/api/auth/session/", { credentials: "include" });
  out.session = sess.status;

  // 3. the failing write, with exactly what the client would send
  const cookie = decodeURIComponent((document.cookie.split("; ").find(c => c.startsWith("ums_mart_csrftoken")) || "=").split("=")[1] || "");
  const post = await fetch(`${api}/cart/items/`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(cookie ? { "X-CSRFToken": cookie } : {}),
      "X-Guest-Cart": "diagnostic-probe",
    },
    body: JSON.stringify({ product: 1, quantity: 1 }),
  });
  out.post = { status: post.status, body: await post.json().catch(() => "(not json)") };

  console.log(JSON.stringify(out, null, 2));
  console.table({ pageHost: out.host, csrfCookie: out.csrfCookie ? "yes" : "no" });
})();
```

Send me the printed object (or read it yourself against the table below).

## Reading the answer

| What you see | Meaning | Fix |
|---|---|---|
| `csrfCookie: "(missing)"` and it stays missing after the endpoint call | The browser **refuses to store** the CSRF cookie. Classic causes: you opened the store on `http://<LAN-IP>:5173` (not `localhost`), a Secure cookie over plain http, or site data is blocked. | Use `http://localhost:5173`, clear "Block all cookies / third-party cookies" for the site. |
| `csrfCookie` present but `post.body.details.reason === "token_mismatch"` | Stale token — the API and the cookie disagree. | Already auto-healed by the client; if you still see it, the build is older than the retry — rebuild (`npm run build`) or restart `npm run dev`. |
| `details.reason === "origin_mismatch"` | Your page's origin is not in `CSRF_TRUSTED_ORIGINS`. | Add it to `backend/.env` (`CSRF_TRUSTED_ORIGINS=http://192.168.1.5:5173`), restart the API. |
| `details.reason === "referer_missing"` | The browser stripped the Referer (strict referrer policy / proxy). | Loosen the referrer policy or use `localhost`. |
| `post.status === 401` (`not_authenticated`) | The endpoint needs a session and you're a guest. | Not a CSRF problem — sign in first. |
| `post.status === 201` but the UI still errored | The failing call was a **different** request. | Check the Network tab: filter `Fetch/XHR`, look for the one that is `403`. |
| `session: 200`, `post.status: 403`, reason says token missing | Session cookie travels but the CSRF cookie does not — they were set by different hosts. | Open store and API on the **same** host name (`localhost` for both, or `127.0.0.1` for both). Never mix. |

## The one-line check that settles "my build or the server?"

```powershell
# in backend — prints the real DRF reason for a CSRF failure without a browser
python manage.py shell -c "from common.exceptions import *; print('module ok')"
```

If the storefront shows the sentence **"Your security token could not be verified …
The server said: CSRF Failed: …"**, you are on the current patch and the text after
"the server said" is the exact DRF reason. If you instead see the old generic
*"Your security token expired, so this change was not saved. Refresh the page and
try again."* with no reason, the browser is running an **older bundle** — rebuild:

```powershell
cd frontend\customer-web
npm run build      # if you serve dist/ (npm run preview)
# or just restart npm run dev after pulling the patch
```

## Most common cause on a Windows dev box

Mixing host names. `localhost:5173` and `127.0.0.1:5173` are **different cookie
jars** to the browser, and `CSRF_TRUSTED_ORIGINS` lists them as different origins.
Pick one and stay on it:

```
http://localhost:5173   storefront
http://localhost:5174   admin
http://127.0.0.1:8000   API  (never call this from the browser; the Vite proxy does)
```
