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
  const headers = { "Content-Type": "application/json" };

  if (UNSAFE.has(method)) {
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
  verifyMfa: (code) => request("/admin/verify-mfa/", { body: { code } }),

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
