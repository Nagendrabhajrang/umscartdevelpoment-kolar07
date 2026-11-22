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
  authService,
  clearSession,
  ensureCsrf,
  getStoredUser,
  isSessionDead,
  purgeLegacyStorage,
  storeSession,
} from "../services/authService";
import { getGuestKey } from "../services/guestCart";

/**
 * Who is signed in.
 *
 * ROUND 30: the source of truth is the Django session on the server, not a token
 * in this browser. This provider holds two things:
 *
 *   `user`     - a display summary, so the header renders immediately
 *   `loading`  - true until the first server check comes back
 *
 * On mount it asks `/api/auth/session/` who we are. A 200 restores the shopper
 * with no OTP and no redirect; a 401 means the server has confirmed the session
 * is gone and only then does the app treat them as signed out.
 *
 * Everything that used to end a session by accident is gone: no token expiry
 * check, no refresh call, no local expiry flag. Tabs, refreshes, navigation and
 * a browser closed overnight all keep the session, because a cookie and a
 * database row do not care about any of those things.
 */
const AuthContext = createContext(null);

/* How often an open tab re-confirms the session. Cheap: one indexed lookup. */
const REVALIDATE_MS = 5 * 60 * 1000;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getStoredUser());
  const [loading, setLoading] = useState(true);
  const [sessionLost, setSessionLost] = useState(false);
  const mounted = useRef(true);
  /* Guards against a burst of 401s firing several redirects at once. */
  const confirming = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  /**
   * Asked once on boot, and whenever the tab wakes up.
   *
   * `silent` keeps the UI from flashing a spinner on a background re-check.
   */
  const revalidate = useCallback(async ({ silent = true } = {}) => {
    if (!silent && mounted.current) setLoading(true);

    try {
      const session = await authService.session();
      if (!mounted.current) return null;

      if (session?.user) {
        setUser(session.user);
        storeSession({ user: session.user });
        setSessionLost(false);
        return session.user;
      }
      // A 200 that says "not authenticated" - treat as signed out, not an error.
      setUser(null);
      clearSession();
      return null;
    } catch (error) {
      /*
       * ONLY a 401 ends the session. A network blip, a timeout, a 500 or a proxy
       * hiccup means the server never answered the question, so the honest
       * position is "we do not know" - keep whatever we had and try again later.
       * Signing out on those was the original bug.
       */
      if (isSessionDead(error)) {
        /*
         * Round 32: only claim a session ended if this browser actually had one.
         * A first-time visitor whose gated page answers 401 was never signed in;
         * telling them "your session ended" is both false and alarming.
         */
        const hadSession = Boolean(getStoredUser());
        clearSession();
        if (mounted.current) {
          setUser(null);
          setSessionLost(hadSession);
        }
      }
      return null;
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  /* Boot: purge dead token storage, plant the CSRF cookie, restore the session. */
  useEffect(() => {
    purgeLegacyStorage();
    ensureCsrf().finally(() => revalidate({ silent: false }));
  }, [revalidate]);

  /**
   * The API layer raises this on a confirmed 401 from an account endpoint.
   * Same rule: the server already said no, so reflect that - once.
   */
  useEffect(() => {
    const onInvalid = () => {
      if (confirming.current) return;
      confirming.current = true;
      /* Same rule as revalidate: no prior session, no "session ended" claim. */
      const hadSession = Boolean(getStoredUser());
      clearSession();
      if (mounted.current) {
        setUser(null);
        setSessionLost(hadSession);
      }
      setTimeout(() => {
        confirming.current = false;
      }, 1000);
    };
    window.addEventListener("ums:session-invalid", onInvalid);
    return () => window.removeEventListener("ums:session-invalid", onInvalid);
  }, []);

  /**
   * A session can expire server-side while a tab sits open for a week, so a
   * sleeping tab re-checks when it comes back. This is a confirmation, not an
   * expiry timer: nothing here can log anyone out on its own.
   */
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

  const sendOtp = useCallback(
    (mobileNumber) => authService.sendOtp(mobileNumber),
    [],
  );

  const resendOtp = useCallback(
    (mobileNumber) => authService.resendOtp(mobileNumber),
    [],
  );

  /**
   * Exchange the SMS code for a session.
   *
   * The response sets the HttpOnly session cookie. There is no token to store -
   * only the user summary the header needs.
   *
   * Round 27 behaviour preserved: the guest basket key rides along so the server
   * folds the anonymous cart into this account inside the same request.
   */
  const verifyOtp = useCallback(async (mobileNumber, code) => {
    const data = await authService.verifyOtp(mobileNumber, code, getGuestKey());

    /*
     * Round 32: the code being accepted is NOT proof that a session exists.
     *
     * The session is an HttpOnly cookie, and a browser can accept the OTP and
     * still refuse that cookie - a third-party/storage-partitioned context (the
     * preview iframe), SameSite blocking, ITP, private mode. The server then
     * answers 200 with no browser-identifying state, every later request still
     * runs as a guest, and anything that "cleans up after login" wipes the guest
     * basket that had just been merged. That is how 2 items become 0.
     *
     * So the login is only completed once the server confirms the cookie works.
     * If it does not, nothing is cleared locally and the guest cart is intact.
     */
    let verified = null;
    try {
      verified = await authService.session();
    } catch {
      verified = null;
    }

    if (!verified?.user) {
      // The OTP was right but no session was established. Keep local state and
      // the guest key exactly as they were, and tell the page to explain it.
      const err = new Error(
        "Your browser didn't keep the sign-in cookie, so we couldn't sign you in. " +
          "Your cart is still saved. Please allow cookies for this site and try again.",
      );
      err.code = "session_cookie_blocked";
      throw err;
    }

    storeSession({ user: verified.user });
    setUser(verified.user);
    setSessionLost(false);
    return { ...data, user: verified.user };
  }, []);

  /**
   * Explicit logout. The server flushes the session; this only clears the local
   * display cache.
   *
   * The local state is cleared even if the request fails: a shopper who pressed
   * "sign out" must not be left looking signed in. But note this is the *only*
   * path that ends a session without the server saying so - nothing automatic
   * ever reaches here.
   */
  const signOut = useCallback(async ({ allDevices = false } = {}) => {
    try {
      await (allDevices ? authService.logoutAll() : authService.logout());
    } catch {
      /* The session may already be gone; the local clear below still applies. */
    } finally {
      clearSession();
      setUser(null);
      setSessionLost(false);
    }
  }, []);

  const updateProfile = useCallback(async (patch) => {
    const profile = await authService.updateProfile(patch);
    setUser(profile);
    storeSession({ user: profile });
    return profile;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      /*
       * Signed in means "the server told us who this is". No token check: there
       * is no token. The user object only exists because a session lookup
       * succeeded.
       */
      isAuthenticated: Boolean(user),
      sessionLost,
      sessionExpired: sessionLost,
      mobileNumber: user?.mobile_number ?? null,
      displayName: user?.display_name ?? null,
      sendOtp,
      resendOtp,
      verifyOtp,
      signOut,
      updateProfile,
      revalidate,
    }),
    [
      user,
      loading,
      sessionLost,
      sendOtp,
      resendOtp,
      verifyOtp,
      signOut,
      updateProfile,
      revalidate,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export default AuthContext;
