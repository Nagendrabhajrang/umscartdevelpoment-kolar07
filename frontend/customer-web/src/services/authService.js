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
  purgeLegacyStorage();
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

  if (csrf && UNSAFE.has(method)) {
    // Make sure the cookie exists before we try to echo it.
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
  verifyOtp: (mobileNumber, code, guestKey) =>
    request("/customer/verify-otp/", {
      body: { mobile_number: mobileNumber, code },
      headers: guestKey ? { "X-Guest-Cart": guestKey } : undefined,
    }),

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

  logout: () => request("/customer/logout/"),

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
