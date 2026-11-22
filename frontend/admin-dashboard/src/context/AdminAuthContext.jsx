import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  adminAuthService,
  clearAdminSession,
  ensureCsrf,
  getStoredAdmin,
  isSessionDead,
  purgeLegacyStorage,
  storeAdminSession,
} from "../services/adminAuthService";

/**
 * The admin session.
 *
 * Holds the account between the two login steps, because the MFA challenge is a
 * continuation of the password step - not a new login. Nothing about the
 * password or the OTP is retained after the flow completes.
 */
const AdminAuthContext = createContext(null);

const REVALIDATE_MS = 2 * 60 * 1000;

export function AdminAuthProvider({ children }) {
  const [admin, setAdmin] = useState(() => getStoredAdmin());
  const [loading, setLoading] = useState(true);
  const [sessionLost, setSessionLost] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  /**
   * Confirm the session with the server.
   *
   * Round 30: there is no local token to test first. The session is an HttpOnly
   * cookie, so "am I signed in?" is a question only the server can answer - and
   * only a 401 is allowed to make this provider sign the operator out.
   */
  const revalidate = useCallback(async ({ silent = true } = {}) => {
    if (!silent && mounted.current) setLoading(true);
    try {
      const session = await adminAuthService.session();
      if (mounted.current) {
        // The session endpoint returns the account under `user`-ish fields; keep
        // the stored profile and only confirm the session is alive.
        setSessionLost(false);
        setLoading(false);
        return session;
      }
      return session;
    } catch (error) {
      if (isSessionDead(error)) {
        // Round 36: only report a *lost* session if this browser actually had
        // one. A first-time visitor whose session probe answers 401 was never
        // signed in; telling them their session ended is false, and the old
        // wording ("signed in somewhere else") was doubly wrong - multiple
        // sessions are allowed on purpose.
        const hadSession = Boolean(getStoredAdmin());
        clearAdminSession();
        if (mounted.current) {
          setAdmin(null);
          setSessionLost(hadSession);
        }
      }
      return null;
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Drop any token left by a pre-session build, plant the CSRF cookie, then
    // ask the server who we are.
    purgeLegacyStorage();
    ensureCsrf().finally(() => revalidate({ silent: false }));
  }, [revalidate]);

  /* The API layer raises this on a confirmed 401 from a protected endpoint. */
  useEffect(() => {
    const onInvalid = () => {
      const hadSession = Boolean(getStoredAdmin());
      clearAdminSession();
      if (mounted.current) {
        setAdmin(null);
        setSessionLost(hadSession);
      }
    };
    window.addEventListener("ums:admin-session-invalid", onInvalid);
    return () =>
      window.removeEventListener("ums:admin-session-invalid", onInvalid);
  }, []);

  useEffect(() => {
    const onFocus = () => revalidate();
    const onVisible = () => {
      if (document.visibilityState === "visible") onFocus();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(onFocus, REVALIDATE_MS);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }, [revalidate]);

  /** Step 1: verify the password. Returns the challenge, mints nothing. */
  const startLogin = useCallback(
    (username, password) => adminAuthService.login(username, password),
    [],
  );

  const resendMfa = useCallback(
    (username) => adminAuthService.resendMfaOtp(username),
    [],
  );

  /** Step 2: the emailed code. Only now does a session exist. */
  const completeLogin = useCallback(async (code) => {
    // The response set the HttpOnly session cookie. Store only the summary.
    const data = await adminAuthService.verifyMfa(code);
    storeAdminSession({ user: data.user });
    setAdmin(data.user);
    setSessionLost(false);
    return data;
  }, []);

  const signOut = useCallback(async ({ allDevices = false } = {}) => {
    try {
      await (allDevices ? adminAuthService.logoutAll() : adminAuthService.logout());
    } catch {
      // Clearing the client is what matters; a dead server must not trap a user
      // in a session they asked to end.
    } finally {
      clearAdminSession();
      setAdmin(null);
      setSessionLost(false);
    }
  }, []);

  const value = useMemo(
    () => ({
      admin,
      loading,
      // Signed in means the server confirmed it. There is no token to check.
      isAuthenticated: Boolean(admin),
      sessionLost,
      displayName: admin?.display_name || admin?.username || "Administrator",
      username: admin?.username ?? null,
      email: admin?.email ?? null,
      role: admin?.role ?? null,
      startLogin,
      resendMfa,
      completeLogin,
      signOut,
      revalidate,
    }),
    [admin, loading, sessionLost, startLogin, resendMfa, completeLogin, signOut, revalidate],
  );

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>;
}

export function useAdminAuth() {
  const ctx = useContext(AdminAuthContext);
  if (!ctx) throw new Error("useAdminAuth must be used inside <AdminAuthProvider>");
  return ctx;
}

export default AdminAuthContext;
