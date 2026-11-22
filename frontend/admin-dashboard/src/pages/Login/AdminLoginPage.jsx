import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAdminAuth } from "../../context/AdminAuthContext";
import { adminAuthService } from "../../services/adminAuthService";

/**
 * Administrator sign-in.
 *
 * Three screens behind one component, because they are one continuous flow:
 *
 *   password -> email code -> dashboard
 *
 * and a separate `forgot` screen that shares nothing with the sign-in path.
 * There is no username lookup on the client: an unknown username and a wrong
 * password are the same 401 from the API, and the UI repeats that by showing one
 * message.
 */

const RESEND_SECONDS = 60;

const fieldClass =
  "h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-900 " +
  "placeholder:text-slate-400 focus:border-brand-500 focus:outline-none " +
  "focus:ring-2 focus:ring-brand-500/20 disabled:bg-slate-50";

export default function AdminLoginPage() {
  const { startLogin, completeLogin, resendMfa, isAuthenticated, sessionLost } =
    useAdminAuth();
  const navigate = useNavigate();

  const [screen, setScreen] = useState("password"); // password | mfa | forgot
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [emailHint, setEmailHint] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [cooldown, setCooldown] = useState(0);

  // Forgot-password sub-flow.
  const [forgotEmail, setForgotEmail] = useState("");
  const [resetToken, setResetToken] = useState(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const codeRef = useRef(null);

  useEffect(() => {
    if (isAuthenticated) navigate("/", { replace: true });
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const timer = window.setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  useEffect(() => {
    if (screen === "mfa") codeRef.current?.focus();
  }, [screen]);

  const resetMessages = () => {
    setError(null);
    setNotice(null);
  };

  /* ---------------- step 1: password ---------------- */
  const handlePassword = async (event) => {
    event.preventDefault();
    resetMessages();
    if (!username.trim() || !password) {
      setError("Enter your username and password.");
      return;
    }
    setBusy(true);
    try {
      const data = await startLogin(username.trim(), password);
      setEmailHint(data?.email_hint || "");
      setDevCode(data?.dev_otp || null);
      setScreen("mfa");
      setCooldown(RESEND_SECONDS);
      // The password is not needed again; drop it from memory.
      setPassword("");
    } catch (e) {
      setError(e?.message || "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  /* ---------------- step 2: email code ---------------- */
  const handleCode = async (event) => {
    event.preventDefault();
    resetMessages();
    if (code.length !== 6) {
      setError("Enter the 6-digit code from your email.");
      return;
    }
    setBusy(true);
    try {
      await completeLogin(code);
      navigate("/", { replace: true });
    } catch (e) {
      setCode("");
      codeRef.current?.focus();
      setError(e?.message || "That code did not work.");
    } finally {
      setBusy(false);
    }
  };

  const handleResend = async () => {
    if (cooldown > 0) return;
    resetMessages();
    setBusy(true);
    try {
      const data = await resendMfa(username.trim());
      setDevCode(data?.dev_otp || null);
      setCode("");
      setCooldown(RESEND_SECONDS);
      setNotice("A new code has been sent.");
    } catch (e) {
      setError(e?.message || "Could not resend the code.");
      if (e?.details?.retry_after_seconds) setCooldown(e.details.retry_after_seconds);
    } finally {
      setBusy(false);
    }
  };

  /* ---------------- forgot password ---------------- */
  const handleForgotRequest = async (event) => {
    event.preventDefault();
    resetMessages();
    if (!forgotEmail.trim()) {
      setError("Enter the email address on the admin account.");
      return;
    }
    setBusy(true);
    try {
      const data = await adminAuthService.forgotPassword(forgotEmail.trim());
      setDevCode(data?.dev_otp || null);
      // The API is deliberately vague here, and so is the UI.
      setNotice(data?.message || "If that email is registered, a reset code has been sent.");
      setStep("reset-code");
    } catch (e) {
      // Even a failure must not reveal whether the address exists.
      setNotice("If that email is registered, a reset code has been sent.");
    } finally {
      setBusy(false);
    }
  };

  const [forgotStep, setStep] = useState("request"); // request | reset-code | new-password

  const handleResetCode = async (event) => {
    event.preventDefault();
    resetMessages();
    if (code.length !== 6) {
      setError("Enter the 6-digit code.");
      return;
    }
    setBusy(true);
    try {
      const data = await adminAuthService.verifyResetOtp(forgotEmail.trim(), code);
      setResetToken(data?.reset_token || null);
      setCode("");
      setStep("new-password");
    } catch (e) {
      setError(e?.message || "That code did not work.");
    } finally {
      setBusy(false);
    }
  };

  const handleNewPassword = async (event) => {
    event.preventDefault();
    resetMessages();
    if (newPassword.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("The two passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await adminAuthService.resetPassword(resetToken, newPassword, confirmPassword);
      setNotice("Password updated. Sign in with your new password.");
      setNewPassword("");
      setConfirmPassword("");
      setResetToken(null);
      setDevCode(null);
      setStep("request");
      setScreen("password");
    } catch (e) {
      setError(e?.message || "Could not reset the password.");
    } finally {
      setBusy(false);
    }
  };

  /* ---------------- render ---------------- */

  const heading =
    screen === "mfa"
      ? "Two-step verification"
      : screen === "forgot"
        ? "Reset your password"
        : "UMS Mart admin";

  const subheading =
    screen === "mfa"
      ? emailHint
        ? `Enter the code sent to ${emailHint}`
        : "Enter the code sent to the admin email"
      : screen === "forgot"
        ? "We'll email a code. If the address isn't registered you'll see the same message."
        : "Sign in with your administrator credentials";

  return (
    <div className="grid min-h-screen place-items-center bg-slate-100 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-600 text-xl font-black text-white">
            U
          </span>
          <div>
            <p className="text-lg font-extrabold tracking-tight text-slate-900">UMS Mart</p>
            <p className="text-xs font-medium text-slate-500">Store administration</p>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <h1 className="text-lg font-extrabold tracking-tight text-slate-900">{heading}</h1>
          <p className="mt-1 text-xs text-slate-500">{subheading}</p>

          {sessionLost && screen === "password" ? (
            <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-900">
              Your session ended. Please sign in again to continue.
            </p>
          ) : null}

          {error ? (
            <p
              role="alert"
              className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700"
            >
              {error}
            </p>
          ) : null}
          {notice && !error ? (
            <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800">
              {notice}
            </p>
          ) : null}

          {/* ---------- password ---------- */}
          {screen === "password" ? (
            <form onSubmit={handlePassword} className="mt-5 space-y-4">
              <div>
                <label
                  htmlFor="username"
                  className="mb-1.5 block text-xs font-semibold text-slate-700"
                >
                  Username
                </label>
                <input
                  id="username"
                  name="username"
                  autoComplete="username"
                  autoFocus
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={fieldClass}
                  placeholder="admin"
                />
              </div>
              <div>
                <label
                  htmlFor="password"
                  className="mb-1.5 block text-xs font-semibold text-slate-700"
                >
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={fieldClass}
                  placeholder="••••••••"
                />
              </div>

              <button
                type="submit"
                disabled={busy}
                className="h-11 w-full rounded-xl bg-brand-600 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Checking…" : "Continue"}
              </button>

              <button
                type="button"
                onClick={() => {
                  resetMessages();
                  setStep("request");
                  setScreen("forgot");
                }}
                className="w-full text-center text-xs font-semibold text-slate-500 hover:text-slate-800"
              >
                Forgot your password?
              </button>
            </form>
          ) : null}

          {/* ---------- mfa ---------- */}
          {screen === "mfa" ? (
            <form onSubmit={handleCode} className="mt-5 space-y-4">
              <div>
                <label
                  htmlFor="mfa-code"
                  className="mb-1.5 block text-xs font-semibold text-slate-700"
                >
                  6-digit code
                </label>
                <input
                  id="mfa-code"
                  ref={codeRef}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  maxLength={6}
                  className="h-14 w-full rounded-xl border border-slate-300 bg-white text-center text-2xl font-bold tracking-[0.5em] text-slate-900 placeholder:tracking-[0.3em] placeholder:text-slate-300 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                  placeholder="••••••"
                />
              </div>

              {devCode ? (
                <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                  <span className="font-bold uppercase tracking-wide text-slate-500">Dev mode</span>{" "}
                  — code{" "}
                  <span className="font-mono text-sm font-bold text-slate-900">{devCode}</span>
                </p>
              ) : null}

              <button
                type="submit"
                disabled={busy || code.length !== 6}
                className="h-11 w-full rounded-xl bg-brand-600 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Verifying…" : "Verify and sign in"}
              </button>

              <div className="flex items-center justify-between text-xs">
                <button
                  type="button"
                  onClick={() => {
                    resetMessages();
                    setScreen("password");
                    setCode("");
                    setDevCode(null);
                  }}
                  className="font-semibold text-slate-600 hover:text-slate-900"
                >
                  Back
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
          ) : null}

          {/* ---------- forgot: request ---------- */}
          {screen === "forgot" && forgotStep === "request" ? (
            <form onSubmit={handleForgotRequest} className="mt-5 space-y-4">
              <div>
                <label
                  htmlFor="forgot-email"
                  className="mb-1.5 block text-xs font-semibold text-slate-700"
                >
                  Admin email
                </label>
                <input
                  id="forgot-email"
                  type="email"
                  autoComplete="email"
                  autoFocus
                  value={forgotEmail}
                  onChange={(e) => setForgotEmail(e.target.value)}
                  className={fieldClass}
                  placeholder="you@example.com"
                />
              </div>
              <button
                type="submit"
                disabled={busy}
                className="h-11 w-full rounded-xl bg-brand-600 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Sending…" : "Send reset code"}
              </button>
              <button
                type="button"
                onClick={() => {
                  resetMessages();
                  setScreen("password");
                }}
                className="w-full text-center text-xs font-semibold text-slate-500 hover:text-slate-800"
              >
                Back to sign in
              </button>
            </form>
          ) : null}

          {/* ---------- forgot: reset code ---------- */}
          {screen === "forgot" && forgotStep === "reset-code" ? (
            <form onSubmit={handleResetCode} className="mt-5 space-y-4">
              <div>
                <label
                  htmlFor="reset-code"
                  className="mb-1.5 block text-xs font-semibold text-slate-700"
                >
                  6-digit code
                </label>
                <input
                  id="reset-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  maxLength={6}
                  className="h-14 w-full rounded-xl border border-slate-300 bg-white text-center text-2xl font-bold tracking-[0.5em] text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                  placeholder="••••••"
                />
              </div>
              {devCode ? (
                <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                  <span className="font-bold uppercase tracking-wide text-slate-500">Dev mode</span>{" "}
                  — code{" "}
                  <span className="font-mono text-sm font-bold text-slate-900">{devCode}</span>
                </p>
              ) : null}
              <button
                type="submit"
                disabled={busy || code.length !== 6}
                className="h-11 w-full rounded-xl bg-brand-600 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Verifying…" : "Continue"}
              </button>
              <button
                type="button"
                onClick={() => {
                  resetMessages();
                  setScreen("password");
                }}
                className="w-full text-center text-xs font-semibold text-slate-500 hover:text-slate-800"
              >
                Back to sign in
              </button>
            </form>
          ) : null}

          {/* ---------- forgot: new password ---------- */}
          {screen === "forgot" && forgotStep === "new-password" ? (
            <form onSubmit={handleNewPassword} className="mt-5 space-y-4">
              <div>
                <label
                  htmlFor="new-password"
                  className="mb-1.5 block text-xs font-semibold text-slate-700"
                >
                  New password
                </label>
                <input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  autoFocus
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className={fieldClass}
                  placeholder="At least 8 characters"
                />
              </div>
              <div>
                <label
                  htmlFor="confirm-password"
                  className="mb-1.5 block text-xs font-semibold text-slate-700"
                >
                  Confirm new password
                </label>
                <input
                  id="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className={fieldClass}
                  placeholder="Repeat the password"
                />
              </div>
              <button
                type="submit"
                disabled={busy}
                className="h-11 w-full rounded-xl bg-brand-600 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Saving…" : "Set new password"}
              </button>
              <p className="text-center text-[11px] text-slate-500">
                Every session is signed out when the password changes.
              </p>
            </form>
          ) : null}
        </div>

        <p className="mt-6 text-center text-[11px] text-slate-400">
          Authorised staff only. Sign-in attempts are rate limited.
        </p>
      </div>
    </div>
  );
}
