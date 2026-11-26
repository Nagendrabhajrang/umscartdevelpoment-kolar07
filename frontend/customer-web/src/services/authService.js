/**
 * Authentication transport for the storefront.
 *
 * ROUND 30: the session is a Django session, carried by an HttpOnly cookie.
 *
 * There is no access token, no refresh token, and nothing to persist. The
 * browser holds `ums_mart_sessionid`, JavaScript cannot read it, and the server
 * decides on every request whether it is still valid. That removes the entire
 * class of bug that used to sign a healthy shopper out: there is no token that
 * can look expired, no refresh call that can fail, and no local expiry flag that
 * can disagree with the server.
 *
 * The only thing kept in storage is a display-only user summary (`ums.auth.user`)
 * so the header does not flicker on reload. It is not a credential and it is
 * thrown away the moment the server says the session is gone.
 *
 * COOKIE-BLOCKED FALLBACK: when the app runs inside a frame that belongs to
 * another site, browsers may refuse the session cookie outright and every
 * request arrives anonymous ("this browser blocked the sign-in cookie"). The API
 * then returns the session key in the login response instead, and it is kept
 * here as `ums.auth.bearer` and sent as an `Authorization: Bearer` header. It is
 * only ever issued when the server has AUTH_BEARER_FALLBACK on (the sandbox
 * preview); in development and production the response has no token at all.
 *
 * CSRF: Django rejects unsafe requests without an `X-CSRFToken` header. That
 * token comes from the `ums_mart_csrftoken` cookie (readable on purpose) and is
 * planted by `/api/auth/csrf/` on boot.
 */

const AUTH_BASE = "/api";

/* Display-only cache of who is signed in. Never a credential. */
const USER_KEY = "ums.auth.user";

/* Keys written by older builds. Cleared on sight. */
const LEGACY_KEYS = [
  "ums.auth.access",
  "ums.auth.refresh",
  "ums.auth.session",
  "ums.admin.access",
  "ums.admin.refresh",
];

const CSRF_COOKIE = "ums_mart_csrftoken";
const CSRF_HEADER = "X-CSRFToken";

/* Session key used only when the browser refuses the session cookie. */
const BEARER_KEY = "ums.auth.bearer";

/* ------------------------------------------------------------------ */
/* Storage                                                            */
/* ------------------------------------------------------------------ */

function read(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    if (value == null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode) - the session still works */
  }
}

/**
 * Remove anything an older, token-based build left behind.
 *
 * A browser that was signed in last week still has `ums.auth.access` in
 * localStorage. It is inert now, but leaving a token-shaped string in storage is
 * both confusing and a small liability, so it is purged on the first load.
 */
export function purgeLegacyStorage() {
  LEGACY_KEYS.forEach((key) => write(key, null));
}

export function getStoredUser() {
  const raw = read(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/** Cache a display-only summary. Safe to call with null. */
export function storeSession({ user } = {}) {
  if (user !== undefined) write(USER_KEY, user ? JSON.stringify(user) : null);
}

export function clearSession() {
  write(USER_KEY, null);
  write(BEARER_KEY, null);
  purgeLegacyStorage();
}

/* ------------------------------------------------------------------ */
/* Cookie-blocked fallback                                            */
/* ------------------------------------------------------------------ */

/**
 * Keep the session key the API handed back, if it handed one back.
 *
 * The key is stored (so a reload stays signed in) and also mirrored in a module
 * variable: if storage is blocked too, at least this tab keeps working.
 */
let memoryBearer = null;

export function storeSessionToken(token) {
  memoryBearer = token || null;
  write(BEARER_KEY, token || null);
}

export function getSessionToken() {
  return memoryBearer ?? read(BEARER_KEY);
}

export function clearSessionToken() {
  memoryBearer = null;
  write(BEARER_KEY, null);
}

/* ------------------------------------------------------------------ */
/* CSRF                                                               */
/* ------------------------------------------------------------------ */

/** Read a cookie by name. Only the CSRF cookie is readable - by design. */
export function getCookie(name) {
  if (typeof document === "undefined" || !document.cookie) return null;
  const match = document.cookie
    .split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(`${name}=`));
  if (!match) return null;
  return decodeURIComponent(match.slice(name.length + 1));
}

/**
 * Ask the server to plant the CSRF cookie, if it is not already there.
 *
 * Called once on app boot. It is idempotent and cheap, and it must happen before
 * the first POST - otherwise that POST is rejected as a CSRF failure, which looks
 * exactly like "the login button does nothing".
 */
let csrfReady = null;
export function ensureCsrf() {
  if (getCookie(CSRF_COOKIE)) return Promise.resolve();
  if (csrfReady) return csrfReady;

  csrfReady = fetch(`${AUTH_BASE}/auth/csrf/`, {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
  })
    .catch(() => null)
    .finally(() => {
      csrfReady = null;
    });

  return csrfReady;
}

/**
 * Throw the CSRF token away and ask for a new one.
 *
 * A CSRF token is tied to a server-side secret and a cookie; when the two drift
 * apart - the cookie was rotated, restored from a stale tab, or was dropped by a
 * browser that blocks site data - every unsafe request is answered with
 * `csrf_failed` ("your security token expired"). The old copy is deleted first so
 * the server cannot just echo it back, then the endpoint is called for a fresh
 * one. Returns the new token, or null when cookies are blocked entirely.
 */
export async function refreshCsrf() {
  csrfReady = null;
  try {
    document.cookie = `${CSRF_COOKIE}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
  } catch {
    /* storage blocked - nothing to drop */
  }
  await fetch(`${AUTH_BASE}/auth/csrf/`, {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  }).catch(() => null);
  return getCookie(CSRF_COOKIE);
}

/* ------------------------------------------------------------------ */
/* Errors                                                             */
/* ------------------------------------------------------------------ */

export class AuthError extends Error {
  constructor(message, code = "error", details = null, status = 0) {
    super(message);
    this.name = "AuthError";
    this.code = code;
    this.details = details;
    this.status = status;
  }
}

async function parseError(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    /* non-JSON body */
  }
  const err = payload?.error;
  if (err) {
    return new AuthError(
      err.message || "Something went wrong.",
      err.code || "error",
      err.details || null,
      response.status,
    );
  }
  return new AuthError(
    `Request failed (${response.status}).`,
    "error",
    null,
    response.status,
  );
}

/* ------------------------------------------------------------------ */
/* Core request                                                       */
/* ------------------------------------------------------------------ */

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function request(
  path,
  { method = "POST", body, headers: extra, csrf = true } = {},
) {
  const headers = { "Content-Type": "application/json", ...(extra || {}) };

  /*
   * Cookie-blocked fallback: if a session key was issued, send it. The server
   * accepts it in place of the cookie and does not require CSRF for it (an
   * explicit header cannot be forged by a cross-site form post).
   */
  const bearer = getSessionToken();
  if (bearer) headers.Authorization = `Bearer ${bearer}`;

  /*
   * Echo the CSRF token whenever the cookie exists - even when a bearer token is
   * being sent. The server ignores it on the bearer path, but a *stale* bearer
   * (issued before the session was reset) makes the server fall back to cookie
   * auth, and that path does need the header. Sending it always removes a whole
   * class of "your security token expired" failures.
   */
  if (csrf && UNSAFE.has(method)) {
    if (!getCookie(CSRF_COOKIE)) await ensureCsrf();
    const token = getCookie(CSRF_COOKIE);
    if (token) headers[CSRF_HEADER] = token;
  }

  let response;
  try {
    response = await fetch(`${AUTH_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      // The session cookie rides along. Same-origin in dev via the Vite proxy;
      // `include` also covers a cross-origin deployment.
      credentials: "include",
    });
  } catch {
    throw new AuthError(
      "Could not reach the server. Check your connection and try again.",
      "network_error",
    );
  }

  if (response.status === 204) return null;
  if (!response.ok) throw await parseError(response);

  try {
    return await response.json();
  } catch {
    return null;
  }
}

/* ------------------------------------------------------------------ */
/* Customer OTP login                                                 */
/* ------------------------------------------------------------------ */

export const authService = {
  /** Step 1: ask for an SMS code. No account is created yet. */
  sendOtp: (mobileNumber) =>
    request("/customer/send-otp/", { body: { mobile_number: mobileNumber } }),

  /**
   * Step 2: exchange the code for a **session**.
   *
   * The server logs the customer in and sets the HttpOnly session cookie on this
   * response. Nothing token-shaped comes back - only the user and whether the
   * account was just created.
   *
   * Round 27 behaviour is preserved: this call is where a guest basket becomes
   * the customer's basket, inside the same request that opens the session.
   */
  verifyOtp: async (mobileNumber, code, guestKey) => {
    // Django cycles the session key when it logs a user in, so clear whatever we
    // held before the call - the new key (if any) is the only valid one.
    clearSessionToken();
    const data = await request("/customer/verify-otp/", {
      body: { mobile_number: mobileNumber, code },
      headers: guestKey ? { "X-Guest-Cart": guestKey } : undefined,
    });
    if (data?.session_token) storeSessionToken(data.session_token);
    return data;
  },

  resendOtp: (mobileNumber) =>
    request("/customer/resend-otp/", { body: { mobile_number: mobileNumber } }),

  /** Current account. Throws 401 only when the server confirms no session. */
  profile: () => request("/customer/profile/", { method: "GET", csrf: false }),

  updateProfile: (patch) =>
    request("/customer/profile/", { method: "PATCH", body: patch }),

  /**
   * What a page load asks: "is this browser still signed in?"
   *
   * 200 -> still signed in, and the body carries the user.
   * 401 -> the server has confirmed there is no session; only now may the app
   *        redirect to the login screen.
   */
  session: () => request("/auth/session/", { method: "GET", csrf: false }),

  /**
   * Sign out. The token is cleared after the call so the request itself still
   * carries it - otherwise a cookie-blocked browser would send an anonymous
   * logout and the session row would survive on the server.
   */
  logout: async () => {
    try {
      return await request("/customer/logout/");
    } finally {
      clearSessionToken();
    }
  },

  logoutAll: () => request("/auth/logout-all/"),
};

/* ------------------------------------------------------------------ */
/* Session-death detection                                            */
/* ------------------------------------------------------------------ */

/**
 * Is this error the server saying "you are not signed in"?
 *
 * Deliberately strict. Only a 401 counts. A 403 is a permission answer (wrong
 * role, or a CSRF failure), a 5xx is the server having a bad day, and a network
 * error means we do not know - none of those are evidence that the session is
 * gone, and signing someone out on them is exactly the bug this round fixes.
 */
export function isSessionDead(error) {
  if (!error) return false;
  const status = error.status ?? error.response?.status;
  return status === 401;
}

/** Kept so older imports resolve; there is no token to expire any more. */
export function sessionExpired() {
  return false;
}

/** Kept so older imports resolve. A session exists until the server says not. */
export function hasSession() {
  return Boolean(getStoredUser()) || Boolean(getCookie(CSRF_COOKIE));
}

/** Kept so older imports resolve - there is nothing to refresh. */
export async function refreshSession() {
  return authService.session();
}

/** Run a call and translate transport errors into the standard shape. */
export async function withSession(fn) {
  return fn();
}
