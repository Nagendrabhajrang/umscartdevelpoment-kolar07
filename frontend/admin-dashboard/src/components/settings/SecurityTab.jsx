import { useEffect, useState } from "react";
import { KeyRound, LogOut, ShieldCheck } from "lucide-react";

import { useAdminAuth } from "../../context/AdminAuthContext";
import { adminAuthService } from "../../services/adminAuthService";

/**
 * Admin security panel: change password, and sign out of every device.
 *
 * Changing a password needs two proofs, and the backend enforces both: the
 * current password, and a code emailed by `change-password/otp/`. The password is
 * never sent anywhere except that one endpoint, and every field is cleared as
 * soon as the call returns.
 */

const fieldClass =
  "h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-900 " +
  "placeholder:text-slate-400 focus:border-brand-500 focus:outline-none " +
  "focus:ring-2 focus:ring-brand-500/20";

export default function SecurityTab() {
  const { email, username, signOut } = useAdminAuth();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [devCode, setDevCode] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);

  useEffect(() => {
    setError(null);
    setDone(null);
  }, [currentPassword, newPassword, confirmPassword, code]);

  const clearForm = () => {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setCode("");
    setCodeSent(false);
    setDevCode(null);
  };

  const sendCode = async () => {
    setSending(true);
    setError(null);
    setDone(null);
    try {
      const data = await adminAuthService.requestChangeOtp();
      setCodeSent(true);
      setDevCode(data?.dev_otp || null);
    } catch (e) {
      setError(e?.message || "Could not send the confirmation code.");
    } finally {
      setSending(false);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    setDone(null);

    if (!codeSent) {
      setError("Request a confirmation code first.");
      return;
    }
    if (newPassword.length < 8) {
      setError("The new password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("The two new passwords do not match.");
      return;
    }

    setBusy(true);
    try {
      await adminAuthService.changePassword(
        currentPassword,
        code,
        newPassword,
        confirmPassword,
      );
      clearForm();
      setDone("Password changed. Other devices have been signed out.");
    } catch (e) {
      setError(e?.message || "Could not change the password.");
      setCode("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <section className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-700">
            <KeyRound className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-slate-900">Change password</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Signed in as <span className="font-semibold text-slate-700">{username}</span>
              {email ? ` (${email})` : ""}. A confirmation code is emailed before any change.
            </p>
          </div>
        </div>

        {error ? (
          <p
            role="alert"
            className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700"
          >
            {error}
          </p>
        ) : null}
        {done && !error ? (
          <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800">
            {done}
          </p>
        ) : null}

        <form onSubmit={submit} className="mt-4 space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label
                htmlFor="current-password"
                className="mb-1.5 block text-xs font-semibold text-slate-700"
              >
                Current password
              </label>
              <input
                id="current-password"
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className={fieldClass}
                placeholder="Your current password"
              />
            </div>

            <div className="sm:col-span-2">
              <label
                htmlFor="confirm-code"
                className="mb-1.5 block text-xs font-semibold text-slate-700"
              >
                Email confirmation code
              </label>
              <div className="flex gap-2">
                <input
                  id="confirm-code"
                  inputMode="numeric"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  maxLength={6}
                  className={`${fieldClass} font-mono tracking-[0.3em]`}
                  placeholder="••••••"
                />
                <button
                  type="button"
                  onClick={sendCode}
                  disabled={sending}
                  className="shrink-0 rounded-xl border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
                >
                  {sending ? "Sending…" : codeSent ? "Resend" : "Send code"}
                </button>
              </div>
              {devCode ? (
                <p className="mt-2 text-[11px] text-slate-500">
                  Dev mode — code{" "}
                  <span className="font-mono font-bold text-slate-800">{devCode}</span>
                </p>
              ) : null}
            </div>

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
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className={fieldClass}
                placeholder="At least 8 characters"
              />
            </div>
            <div>
              <label
                htmlFor="confirm-new-password"
                className="mb-1.5 block text-xs font-semibold text-slate-700"
              >
                Confirm new password
              </label>
              <input
                id="confirm-new-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={fieldClass}
                placeholder="Repeat it"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="submit"
              disabled={busy || !codeSent}
              className="h-10 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? "Saving…" : "Change password"}
            </button>
            <button
              type="button"
              onClick={clearForm}
              className="h-10 rounded-xl px-3 text-sm font-semibold text-slate-600 transition hover:bg-slate-100"
            >
              Clear
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-600">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            </span>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Sign-ins</h2>
              <p className="mt-0.5 text-xs text-slate-500">
                You can be signed in on several devices at once, and each stays
                signed in for 8 hours. Signing out everywhere stops every device
                from renewing - a device already open stays usable until its
                current 8-hour token runs out.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => signOut({ allDevices: true })}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
            Sign out everywhere
          </button>
        </div>
      </section>
    </div>
  );
}
