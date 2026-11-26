/**
 * Central Axios instance for the UMS Mart API.
 *
 * Every service module imports this. Nothing else creates an Axios instance,
 * so base URL, identity header, error normalisation and logging live in one
 * place.
 *
 * AUTH: every request carries the administrator's bearer token. The legacy
 * `X-Customer-Id` header is still sent because a few read endpoints resolve an
 * acting customer; it is a development seam, not a security boundary, and the
 * token is what the admin endpoints actually authorise on.
 */

import axios from "axios";

import {
  clearAdminSession,
  ensureCsrf,
  getCookie,
  getSessionToken,
  refreshCsrf,
} from "./adminAuthService";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const CUSTOMER_ID = "1"; // admin build acts as customer 1 for identity-scoped reads
const CUSTOMER_STORAGE_KEY = "ums.customerId";

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

const CSRF_COOKIE = "ums_mart_csrftoken";
const CSRF_HEADER = "X-CSRFToken";
const UNSAFE = new Set(["post", "put", "patch", "delete"]);

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 20000,
  headers: { "Content-Type": "application/json" },
  // Round 30: the admin session is an HttpOnly cookie, so every request must be
  // allowed to send credentials.
  withCredentials: true,
  xsrfCookieName: CSRF_COOKIE,
  xsrfHeaderName: CSRF_HEADER,
});

/* ------------------------------------------------------------------ */
/* Request: attach the identity header                                 */
/* ------------------------------------------------------------------ */
api.interceptors.request.use(async (config) => {
  const method = (config.method || "get").toLowerCase();

  // Django's SessionAuthentication requires the CSRF header on unsafe requests.
  // Missing it produces a 403 that must never be mistaken for a dead session.
  if (UNSAFE.has(method)) {
    if (!getCookie(CSRF_COOKIE)) await ensureCsrf();
    const token = getCookie(CSRF_COOKIE);
    if (token) config.headers[CSRF_HEADER] = token;
  }

  /*
   * Cookie-blocked fallback: replay the session key when the API issued one
   * (only happens with AUTH_BEARER_FALLBACK on, i.e. the hosted preview).
   */
  const bearer = getSessionToken();
  if (bearer) config.headers.Authorization = `Bearer ${bearer}`;

  /*
   * Which app this is. The API keeps the dashboard's session in its own cookie
   * (`ums_mart_admin_sessionid`) for requests that say "admin", so signing in
   * here can never replace the shopper's session in the same browser - and the
   * storefront, which sends no such header, is never mistaken for the dashboard.
   */
  config.headers["X-Client"] = "admin";

  config.headers["X-Customer-Id"] = getCustomerId();

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
 * ROUND 30: there is no token to refresh. A 401 means the server processed the
 * request and found no admin session - the one signal that may send the operator
 * back to the login screen. A 403 is a permission or CSRF answer, and a 5xx or
 * network failure tells us nothing, so neither may end the session.
 */
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status;
    const normalised = normaliseError(error);
    const config = error?.config;

    /*
     * Self-heal a stale CSRF token before the operator ever sees it.
     *
     * A settings save (or any PATCH) that fails with `csrf_failed` used to show
     * "your security token expired, refresh the page". The token is not the
     * session: it can be re-fetched mechanically, so the request is replayed once
     * with a fresh one. A second failure is a real CSRF/cookie problem and is
     * reported normally.
     */
    if (
      normalised.code === "csrf_failed" &&
      config &&
      !config._csrfRetried &&
      UNSAFE.has((config.method || "").toLowerCase())
    ) {
      config._csrfRetried = true;
      const fresh = await refreshCsrf();
      if (fresh) {
        config.headers = config.headers || {};
        config.headers[CSRF_HEADER] = fresh;
        return api(config);
      }
    }

    if (status === 401) {
      clearAdminSession();
      window.dispatchEvent(new CustomEvent("ums:admin-session-invalid"));
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

/** Query params for DRF pagination from a page URL (proxy-safe). */
export { pageParams as pageParamsFrom };
