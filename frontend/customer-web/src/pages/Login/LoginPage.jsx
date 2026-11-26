import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import Button from "../../components/common/Button";
import Input from "../../components/common/Input";
import { useAuth } from "../../context/AuthContext";
import { useNotification } from "../../context/NotificationContext";

/**
 * Customer sign-in: mobile number, then a six-digit SMS code.
 *
 * Two steps, one screen - the code step only replaces the form body, so the page
 * never re-mounts and the number typed in step one cannot be lost. There is no
 * password field anywhere: customers never have one.
 */

const RESEND_SECONDS = 60;

/** Normalise whatever the shopper typed to ten digits: 98765 43210 -> 9876543210. */
function toDigits(value) {
  return String(value).replace(/\D/g, "").replace(/^91(?=\d{10}$)/, "").replace(/^0/, "").slice(-10);
}

function maskMobile(mobile) {
  if (!mobile) return "";
  const digits = mobile.replace(/\D/g, "");
  return `+91 ${digits.slice(0, 2)}XXXX${digits.slice(-4)}`;
}

export default function LoginPage() {
  const { sendOtp, resendOtp, verifyOtp, isAuthenticated, sessionLost } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();
  const location = useLocation();

  const [step, setStep] = useState("mobile");
  const [mobile, setMobile] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  const codeRef = useRef(null);
  const digits = toDigits(mobile);
  const valid = digits.length === 10 && /^[6-9]/.test(digits);

  /*
   * Where to go after a successful sign-in.
   *
   * Round 27: back to whatever sent them here. Arriving from checkout means
   * they land on checkout again with the same basket; a voluntary Login click
   * means the homepage, or the page they were reading.
   */
  const cameFromCheckout = location.state?.reason === "checkout";
  const fromState = location.state?.from;
  const redirectTo = fromState
    ? `${fromState.pathname ?? "/"}${fromState.search ?? ""}`
    : "/";

  const cartCount = location.state?.cartCount ?? 0;

  /**
   * One place decides where to go after sign-in.
   *
   * Round 23 rewrite. The basket is no longer replayed through a pending
   * "add to cart" intent - the shopper already added items while signed out,
   * and CartContext merges that guest basket into the account as soon as the
   * session appears. So all this does now is land them on the home page and
   * tell them the basket came with them.
   */
  const finishing = useRef(false);
  const finish = useCallback(() => {
    if (finishing.current) return;
    finishing.current = true;

    notify.success(
      cameFromCheckout
        ? "Signed in. Your cart is waiting at checkout."
        : "Signed in.",
    );
    navigate(redirectTo, {
      replace: true,
      state: location.state?.welcome ?? { justSignedIn: true },
    });
  }, [navigate, redirectTo, location.state, notify, cameFromCheckout]);

  useEffect(() => {
    if (!isAuthenticated) return;
    finish();
  }, [isAuthenticated, finish]);

  // Resend timer.
  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const timer = window.setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  useEffect(() => {
    if (step === "code") codeRef.current?.focus();
  }, [step]);

  const handleSend = async (event) => {
    event?.preventDefault?.();
    if (!valid) {
      setError("Enter a valid 10-digit mobile number starting with 6, 7, 8 or 9.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const data = await sendOtp(digits);
      setDevCode(data?.dev_otp || null);
      setStep("code");
      setCooldown(RESEND_SECONDS);
    } catch (e) {
      setError(e?.message || "Could not send the code. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const handleVerify = async (event) => {
    event?.preventDefault?.();
    if (code.length !== 6) {
      setError("Enter the 6-digit code.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await verifyOtp(digits, code);
      // `finish()` runs when isAuthenticated flips; it performs the pending
      // action (add to cart) or navigates onward.

    } catch (e) {
      setCode("");
      /*
       * `session_cookie_blocked` means the code was right but this browser would
       * not keep the session at all - neither the cookie nor the header token
       * the API also hands back (see docs/SIGNIN_SESSIONS.md). Say so plainly,
       * and reassure the shopper that nothing was lost: the guest cart is
       * untouched by that path.
       */
      setError(
        e?.code === "session_cookie_blocked"
          ? "The code was right, but this browser refused to keep the sign-in session. Your cart is still saved here. Allow cookies and site data for this site, then try again."
          : e?.message || "That code did not work. Try again.",
      );
      if (e?.code !== "session_cookie_blocked") codeRef.current?.focus();
    } finally {
      setBusy(false);
    }
  };

  const handleResend = async () => {
    if (cooldown > 0) return;
    setBusy(true);
    setError(null);
    try {
      const data = await resendOtp(digits);
      setDevCode(data?.dev_otp || null);
      setCode("");
      setCooldown(RESEND_SECONDS);
      setNotice("A new code is on its way.");
    } catch (e) {
      setError(e?.message || "Could not resend the code.");
      if (e?.details?.retry_after_seconds) setCooldown(e.details.retry_after_seconds);
    } finally {
      setBusy(false);
    }
  };

  const backToMobile = () => {
    setStep("mobile");
    setCode("");
    setError(null);
    setNotice(null);
    setDevCode(null);
  };

  return (
    <div className="container-page py-10">
      <div className="mx-auto w-full max-w-md">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <div className="mb-6 flex items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-600 text-lg font-black text-white">
              U
            </span>
            <div>
              <h1 className="text-xl font-extrabold tracking-tight text-slate-900">
                {step === "mobile" ? "Sign in to UMS Mart" : "Enter your code"}
              </h1>
              <p className="text-xs text-slate-500">
                {step === "mobile"
                  ? "We'll text you a 6-digit code - no password needed."
                  : `Sent to ${maskMobile(digits)}`}
              </p>
            </div>
          </div>

          {/* Arriving from checkout: say why, and promise the basket is safe. */}
          {cameFromCheckout && step === "mobile" ? (
            <div className="mb-4 rounded-xl border border-brand-200 bg-brand-50 px-3.5 py-3">
              <p className="text-sm font-bold text-brand-900">
                Login to continue with your order
              </p>
              <p className="mt-0.5 text-xs font-medium text-brand-800">
                {cartCount > 0
                  ? `Your ${cartCount} item${cartCount === 1 ? "" : "s"} ${
                      cartCount === 1 ? "is" : "are"
                    } safe — they will be here when you come back.`
                  : "Your cart is safe and will be here when you come back."}
              </p>
            </div>
          ) : null}

          {sessionLost && step === "mobile" ? (
            <p className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-900">
              Your session ended. Please sign in again to continue.
            </p>
          ) : null}

          {step === "mobile" ? (
            <form onSubmit={handleSend} noValidate>
              <label
                htmlFor="mobile"
                className="mb-1.5 block text-xs font-semibold text-slate-700"
              >
                Mobile number
              </label>
              <div className="flex items-stretch gap-2">
                <span className="grid h-11 shrink-0 place-items-center rounded-xl border border-slate-300 bg-slate-50 px-3 text-sm font-semibold text-slate-600">
                  +91
                </span>
                <input
                  id="mobile"
                  name="mobile"
                  type="tel"
                  inputMode="numeric"
                  autoComplete="tel"
                  autoFocus
                  placeholder="98765 43210"
                  value={mobile}
                  onChange={(e) => {
                    setMobile(e.target.value);
                    setError(null);
                  }}
                  maxLength={15}
                  aria-invalid={error ? "true" : undefined}
                  className={`h-11 w-full min-w-0 rounded-xl border bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 ${
                    error ? "border-rose-400" : "border-slate-300"
                  }`}
                />
              </div>

              {error ? (
                <p className="mt-2 text-xs font-medium text-rose-600" role="alert">
                  {error}
                </p>
              ) : (
                <p className="mt-2 text-xs text-slate-500">
                  New here? An account is created automatically.
                </p>
              )}

              <Button
                type="submit"
                size="lg"
                fullWidth
                className="mt-5"
                loading={busy}
                disabled={busy || !valid}
              >
                Send code
              </Button>
            </form>
          ) : (
            <form onSubmit={handleVerify} noValidate>
              <label
                htmlFor="otp"
                className="mb-1.5 block text-xs font-semibold text-slate-700"
              >
                6-digit code
              </label>
              <input
                id="otp"
                name="otp"
                ref={codeRef}
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="••••••"
                value={code}
                onChange={(e) => {
                  setCode(e.target.value.replace(/\D/g, "").slice(0, 6));
                  setError(null);
                }}
                maxLength={6}
                aria-invalid={error ? "true" : undefined}
                className={`h-14 w-full rounded-xl border bg-white text-center text-2xl font-bold tracking-[0.5em] text-slate-900 placeholder:tracking-[0.3em] placeholder:text-slate-300 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 ${
                  error ? "border-rose-400" : "border-slate-300"
                }`}
              />

              {error ? (
                <p className="mt-2 text-xs font-medium text-rose-600" role="alert">
                  {error}
                </p>
              ) : notice ? (
                <p className="mt-2 text-xs font-medium text-emerald-700">{notice}</p>
              ) : (
                <p className="mt-2 text-xs text-slate-500">
                  The code expires in 5 minutes.
                </p>
              )}

              {devCode ? (
                <p className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                  <span className="font-bold uppercase tracking-wide text-slate-500">
                    Dev mode
                  </span>{" "}
                  — your code is{" "}
                  <span className="font-mono text-sm font-bold text-slate-900">
                    {devCode}
                  </span>
                  . Shown because `AUTH_DEV_MODE` is on and this is a debug build.
                </p>
              ) : null}

              <Button
                type="submit"
                size="lg"
                fullWidth
                className="mt-5"
                loading={busy}
                disabled={busy || code.length !== 6}
              >
                Verify and sign in
              </Button>

              <div className="mt-4 flex items-center justify-between text-xs">
                <button
                  type="button"
                  onClick={backToMobile}
                  className="font-semibold text-slate-600 hover:text-slate-900"
                >
                  Change number
                </button>
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={cooldown > 0 || busy}
                  className="font-semibold text-brand-700 hover:text-brand-800 disabled:cursor-not-allowed disabled:text-slate-400"
                >
                  {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend code"}
                </button>
              </div>
            </form>
          )}
        </div>

        <p className="mt-5 text-center text-xs text-slate-500">
          Looking for the store dashboard?{" "}
          <Link to="/" className="font-semibold text-brand-700 hover:text-brand-800">
            Continue browsing
          </Link>
        </p>
      </div>
    </div>
  );
}
