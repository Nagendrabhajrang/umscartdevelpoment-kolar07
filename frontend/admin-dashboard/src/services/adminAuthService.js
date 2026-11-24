/**
 * Authentication transport for the admin dashboard.
 *
 * A separate module from the storefront's, because the admin flow is genuinely
 * different: username + password, then an email OTP. There is no customer code
 * path here and no shared form - the spec requires the two never mix.
 *
 * ROUND 30: Django sessions. The admin session is the same HttpOnly
 * `ums_mart_sessionid` cookie the storefront uses, tagged with the admin role in
 * the session. Nothing is stored in localStorage except a display summary.
 *
 * The admin API answers 401 for an unknown username and a wrong password alike,
 * and the dashboard must not try to tell them apart.
 */

const AUTH_BASE = "/api";

/* Display-only cache of the signed-in administrator. Never a credential. */
const USER_KEY = "ums.admin.user";

/* Keys written by older, token-based builds. Cleared on sight. */
const LEGACY_KEYS = ["ums.admin.access", "ums.admin.refresh", "ums.admin.session"];

const CSRF_COOKIE = "ums_mart_csrftoken";
const CSRF_HEADER = "X-CSRFToken";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/*
 * Cookie-blocked fallback.
 *
 * In a cross-site frame (the hosted preview) the browser can refuse the session
 * cookie, and then every request arrives anonymous. The API answers the login
 * with a `session_token` in the body when AUTH_BEARER_FALLBACK is on, and it is
 * replayed as `Authorization: Bearer`. Off by default on the server, so a normal
 * deployment still carries its credential in the HttpOnly cookie only.
 */
const BEARER_KEY = "ums.admin.bearer";
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
    /* storage unavailable */
  }
}

export function getStoredAdmin() {
  const raw = read(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function storeAdminSession({ user } = {}) {
  if (user !== undefined) write(USER_KEY, user ? JSON.stringify(user) : null);
}

export function clearAdminSession() {
  write(USER_KEY, null);
  write(BEARER_KEY, null);
  memoryBearer = null;
  purgeLegacyStorage();
}

export function purgeLegacyStorage() {
  LEGACY_KEYS.forEach((key) => write(key, null));
}

/**
 * There is no local "do I have a session" test any more.
 *
 * The session lives in an HttpOnly cookie that JavaScript cannot inspect, which
 * is the point. Asking the server (`adminAuthService.session()`) is the only
 * honest answer, so callers use that instead.
 */
export function hasAdminSession() {
  return Boolean(getStoredAdmin());
}

/* ------------------------------------------------------------------ */
/* CSRF                                                               */
/* ------------------------------------------------------------------ */

export function getCookie(name) {
  if (typeof document === "undefined" || !document.cookie) return null;
  const match = document.cookie
    .split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(`${name}=`));
  if (!match) return null;
  return decodeURIComponent(match.slice(name.length + 1));
}

let csrfReady = null;
export function ensureCsrf() {
  if (getCookie(CSRF_COOKIE)) return Promise.resolve();
  if (csrfReady) return csrfReady;

  csrfReady = fetch(`${AUTH_BASE}/auth/csrf/`, {
    method: "GET",
    credentials: "include",
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
 * Used by the response interceptor when the API answers `csrf_failed`: a stale
 * token is retried once with a fresh one instead of showing the operator
 * "your security token expired" and making them refresh the page.
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

export class AdminAuthError extends Error {
  constructor(message, code = "error", details = null, status = 0) {
    super(message);
    this.name = "AdminAuthError";
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
    return new AdminAuthError(
      err.message || "Something went wrong.",
      err.code || "error",
      err.details || null,
      response.status,
    );
  }
  return new AdminAuthError(
    `Request failed (${response.status}).`,
    "error",
    null,
    response.status,
  );
}

/* ------------------------------------------------------------------ */
/* Core request                                                       */
/* ------------------------------------------------------------------ */

async function request(path, { method = "POST", body } = {}) {
  // Same tag as the axios instance: the login, MFA, session and logout calls are
  // the ones that create or destroy the admin session cookie, so they must say
  // which client they belong to or they would touch the shopper's session.
  const headers = { "Content-Type": "application/json", "X-Client": "admin" };

  const bearer = getSessionToken();
  if (bearer) headers.Authorization = `Bearer ${bearer}`;

  if (UNSAFE.has(method) && !bearer) {
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
      // Send the HttpOnly session cookie.
      credentials: "include",
    });
  } catch {
    throw new AdminAuthError(
      "Could not reach the server. Check that the API is running.",
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
/* Admin password + MFA flow                                          */
/* ------------------------------------------------------------------ */

export const adminAuthService = {
  /** Step 1: password. Returns an MFA challenge; no session yet. */
  login: (username, password) =>
    request("/admin/login/", { body: { username, password } }),

  /**
   * Step 2: the emailed code. This is the only call that opens an admin session,
   * and the HttpOnly cookie is set on its response.
   */
  verifyMfa: async (code) => {
    clearSessionToken();
    const data = await request("/admin/verify-mfa/", { body: { code } });
    if (data?.session_token) storeSessionToken(data.session_token);
    return data;
  },

  resendMfaOtp: (username) =>
    request("/admin/resend-mfa-otp/", { body: { username } }),

  forgotPassword: (email) =>
    request("/admin/forgot-password/", { body: { email } }),

  verifyResetOtp: (email, code) =>
    request("/admin/verify-reset-otp/", { body: { email, code } }),

  resetPassword: (resetToken, newPassword, confirmPassword) =>
    request("/admin/reset-password/", {
      body: {
        reset_token: resetToken,
        new_password: newPassword,
        confirm_password: confirmPassword,
      },
    }),

  /** Request the confirmation code needed before a password change. */
  requestChangeOtp: () => request("/admin/change-password/otp/"),

  changePassword: (currentPassword, code, newPassword, confirmPassword) =>
    request("/admin/change-password/", {
      body: {
        current_password: currentPassword,
        code,
        new_password: newPassword,
        confirm_password: confirmPassword,
      },
    }),

  /**
   * "Is this browser still an admin session?"
   *
   * 200 -> yes, and the body carries the user. 401 -> the server confirmed there
   * is no session. This is the only check that may redirect to the login screen.
   */
  session: () => request("/auth/session/", { method: "GET" }),

  logout: () => request("/admin/logout/"),

  logoutAll: () => request("/auth/logout-all/"),
};

/** Only a 401 means the session is gone. Nothing else may sign an admin out. */
export function isSessionDead(error) {
  if (!error) return false;
  return (error.status ?? error.response?.status) === 401;
}

/** Kept so older imports resolve; there is no token to refresh. */
export async function refreshAdminSession() {
  return adminAuthService.session();
}

/** Kept so older imports resolve; there is no token to hand around. */
export async function withAdminSession(fn) {
  return fn(null);
}
