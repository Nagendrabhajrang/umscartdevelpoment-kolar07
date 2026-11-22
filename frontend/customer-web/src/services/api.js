/**
 * Central Axios instance for the UMS Mart API.
 *
 * Every service module imports this. Nothing else creates an Axios instance, so
 * base URL, CSRF handling, error normalisation and logging live in one place.
 *
 * AUTH (round 30): Django sessions. The browser sends the HttpOnly
 * `ums_mart_sessionid` cookie automatically, and this instance is configured with
 * `withCredentials: true` so it does so on cross-origin deployments too. There
 * is no Authorization header any more - nothing here holds a token.
 *
 * The `X-Guest-Cart` header is unchanged: it names an anonymous basket so a
 * visitor can fill a cart before signing in, and the server folds that basket
 * into the account at the moment the session is created.
 */

import axios from "axios";

import { clearSession, ensureCsrf, getCookie } from "./authService";
import { getGuestKey } from "./guestCart";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const CUSTOMER_ID = import.meta.env.VITE_DEFAULT_CUSTOMER_ID || "1";
const CUSTOMER_STORAGE_KEY = "ums.customerId";

const CSRF_COOKIE = "ums_mart_csrftoken";
const CSRF_HEADER = "X-CSRFToken";
const UNSAFE = new Set(["post", "put", "patch", "delete"]);

/** The acting customer id. Persisted so a reload keeps the same cart. */
export function getCustomerId() {
  try {
    return localStorage.getItem(CUSTOMER_STORAGE_KEY) || CUSTOMER_ID;
  } catch {
    return CUSTOMER_ID;
  }
}

export function setCustomerId(id) {
  try {
    localStorage.setItem(CUSTOMER_STORAGE_KEY, String(id));
  } catch {
    /* storage unavailable - fall back to the env default */
  }
}

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 20000,
  headers: { "Content-Type": "application/json" },
  // Send the session cookie. Required for cookie auth to work at all, and
  // harmless when everything is same-origin.
  withCredentials: true,
  // Let axios read the CSRF cookie header (needed only cross-origin).
  xsrfCookieName: CSRF_COOKIE,
  xsrfHeaderName: CSRF_HEADER,
});

/* ------------------------------------------------------------------ */
/* Request: CSRF + guest basket                                       */
/* ------------------------------------------------------------------ */
api.interceptors.request.use(async (config) => {
  const method = (config.method || "get").toLowerCase();

  /*
   * CSRF. Django's SessionAuthentication refuses an unsafe request that does not
   * echo the CSRF token, and it refuses it as a 403 - which, if it were treated
   * as a session problem, would sign the shopper out for a missing cookie. So the
   * token is attached eagerly and the cookie is planted on demand.
   */
  if (UNSAFE.has(method)) {
    if (!getCookie(CSRF_COOKIE)) await ensureCsrf();
    const token = getCookie(CSRF_COOKIE);
    if (token) config.headers[CSRF_HEADER] = token;
  }

  /*
   * Guest basket key.
   *
   * Always sent, signed in or not. When a session exists the server resolves the
   * basket from the session and ignores this; when it does not, this names the
   * anonymous basket. Sending it unconditionally means a request that races a
   * sign-out degrades to the guest basket instead of failing with
   * `customer_context_required`.
   */
  config.headers["X-Guest-Cart"] = getGuestKey();

  // Let the browser set the multipart boundary for file uploads.
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

/* ------------------------------------------------------------------ */
/* Response: unwrap + normalise errors                                 */
/* ------------------------------------------------------------------ */

/**
 * The backend always answers errors with
 *   { error: { code, message, details?, status } }
 * This turns anything else (network failure, HTML error page, timeout) into
 * the same shape so UI code only ever handles one form.
 */
export function normaliseError(error) {
  if (error?.response) {
    const { status, data } = error.response;
    if (data?.error) {
      return {
        status,
        code: data.error.code || "error",
        message: data.error.message || "Something went wrong.",
        details: data.error.details || null,
      };
    }
    if (typeof data === "string") {
      return { status, code: "error", message: data.slice(0, 300), details: null };
    }
    return {
      status,
      code: "error",
      message: data?.detail || `Request failed with status ${status}.`,
      details: data || null,
    };
  }
  if (error?.code === "ECONNABORTED") {
    return {
      status: 0,
      code: "timeout",
      message: "The server took too long to respond. Please try again.",
      details: null,
    };
  }
  return {
    status: 0,
    code: "network_error",
    message:
      "Cannot reach the UMS Mart API. Is the backend running on port 8000?",
    details: null,
  };
}

/**
 * Response handling.
 *
 * ROUND 30: there is nothing to refresh.
 *
 * With session auth a 401 has exactly one meaning: the server processed the
 * request and found no valid session. That is the *only* thing allowed to end a
 * signed-in state. Previously this interceptor tried to rotate a token on every
 * 401, and every way that rotation could fail - a dropped request, a cache miss,
 * a clock skew - was another way to sign a healthy shopper out. All of it is gone.
 *
 * What remains:
 *   - 401 on an account endpoint -> tell the app once, via `ums:session-invalid`.
 *   - 403 -> a permission/CSRF answer, NOT a session problem. Never signs out.
 *   - 5xx / timeout / network -> transient. Never signs out.
 */
export function needsAccount(url) {
  return /\/(cart|wishlist|orders|addresses|profile|support)/.test(url || "");
}

let notifying = false;

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const normalised = normaliseError(error);
    const url = error?.config?.url;

    /*
     * A 401 is decisive: the server confirmed there is no session. Clear the
     * display cache so the header stops claiming someone is signed in, and tell
     * the app to route to sign-in.
     *
     * The public catalogue must keep working for a visitor with no session, so a
     * 401 there is not broadcast as a sign-out - it is just an error.
     */
    if (status === 401 && needsAccount(url)) {
      clearSession();
      normalised.requiresSignIn = true;
      normalised.message =
        normalised.message || "Please sign in to continue.";

      if (!notifying) {
        notifying = true;
        setTimeout(() => {
          notifying = false;
          window.dispatchEvent(new CustomEvent("ums:session-invalid"));
        }, 50);
      }
    }

    /*
     * `customer_context_required` used to mean "we cannot tell whose data this
     * is", which with a token in play could mean the token had expired. With
     * sessions there is no expiring credential: either a session exists, in which
     * case the server resolves the customer from it, or it does not, in which
     * case the answer is 401 and handled above. A 400 here means the caller
     * genuinely sent no identity - a guest hitting a customer-only endpoint - so
     * it gets the ordinary "sign in to continue" treatment without touching the
     * session.
     */
    if (
      normalised?.code === "customer_context_required" &&
      needsAccount(url)
    ) {
      normalised.requiresSignIn = true;
      normalised.message = "Please sign in to continue.";
    }

    return Promise.reject(normalised);
  },
);

/* ------------------------------------------------------------------ */
/* Thin helpers used by every service                                  */
/* ------------------------------------------------------------------ */

/** GET with query params, returns `data`. */
export async function get(url, params) {
  const { data } = await api.get(url, { params });
  return data;
}

/**
 * GET a list, normalised to `{ results, count, next, previous }`.
 *
 * Not every list endpoint in this API is paginated: `/orders/mine/`,
 * `/support/mine/`, `/addresses/mine/`, `/banners/live/` and the product
 * "featured"/"related" routes return plain arrays. Callers should not have to
 * care, so a bare array is wrapped into the same shape here - once.
 */
export async function getPaginated(url, params) {
  const data = await get(url, params);
  if (Array.isArray(data)) {
    return { results: data, count: data.length, next: null, previous: null };
  }
  return {
    results: data?.results ?? [],
    count: data?.count ?? 0,
    next: data?.next ?? null,
    previous: data?.previous ?? null,
  };
}

export async function post(url, body, config) {
  const { data } = await api.post(url, body, config);
  return data;
}

export async function patch(url, body) {
  const { data } = await api.patch(url, body);
  return data;
}

export async function put(url, body) {
  const { data } = await api.put(url, body);
  return data;
}

export async function del(url) {
  const { data } = await api.delete(url);
  return data;
}

/**
 * Multipart upload helper. `fields` may contain strings, numbers, files or
 * arrays; arrays are appended under the same key so DRF receives a list.
 */
export async function postMultipart(url, fields, method = "post") {
  const form = new FormData();
  Object.entries(fields).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    if (Array.isArray(value)) {
      value.forEach((v) => form.append(key, v));
    } else {
      form.append(key, value);
    }
  });
  const { data } = await api[method](url, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/** Turn a DRF page URL into just its query string, for proxy-safe paging. */
export function pageParams(pageUrl) {
  if (!pageUrl) return {};
  try {
    const url = new URL(pageUrl, window.location.origin);
    return Object.fromEntries(url.searchParams.entries());
  } catch {
    return {};
  }
}

/** Absolute media URL for images served by Django. */
export function mediaUrl(path) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  const base = BASE_URL.replace(/\/api\/v1\/?$/, "");
  return `${base}${path.startsWith("/") ? "" : "/"}${path}`;
}

export const API_BASE_URL = BASE_URL;
