import { useEffect, useMemo, useState } from "react";

import { paymentService } from "../../services/paymentService";
import { useNotification } from "../../context/NotificationContext";
import Button from "../common/Button";
import Input from "../common/Input";
import Modal from "../common/Modal";
import { formatMoney } from "../../utils/format";

/**
 * "Scan, pay, then tell us which payment it was" popup - the whole UPI step in
 * one place.
 *
 * Order of the screen is deliberate, because it is the order the customer does
 * it in:
 *
 *   1. the store's **QR code** (plus the UPI ID, copy button and the amount), so
 *      they can pay without leaving the popup;
 *   2. **Transaction ID / UTR** - required;
 *   3. **Phone / Google Pay number** - optional.
 *
 * `blocking` mode has no close button, no backdrop click and no Escape, and the
 * submit button stays disabled until a usable transaction ID is typed. That is
 * what stops a UPI order from being created and then abandoned: the order page
 * only opens once the reference is saved.
 *
 * Two shapes, one component:
 *
 *   with a paymentId   - an existing UPI order that still needs its reference;
 *                        submitting saves it to /payments/{id}/submit-proof/
 *   without one        - the checkout step, before the order exists: the values
 *                        are collected here and handed back through onCollected,
 *                        so the reference is in hand before "Place order" can run
 *
 * This component is only ever mounted for UPI orders - cash on delivery shows no
 * QR and no UPI ID anywhere, by design.
 */

const MIN_REFERENCE = 6;

export default function UpiReferenceModal({
  open,
  onClose,
  paymentId,
  amount,
  orderNumber,
  upiId,
  payeeName,
  qrUrl,
  onSubmitted,
  onCollected,
  initialReference = "",
  initialMobile = "",
  blocking = false,
}) {
  const { notify } = useNotification();
  const [reference, setReference] = useState("");
  const [payerMobile, setPayerMobile] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  // A fresh popup must not show the previous attempt's values - except what the
  // customer already typed, so "Change" opens on their own reference.
  useEffect(() => {
    if (open) {
      setError("");
      setBusy(false);
      setCopied(false);
      setReference(initialReference || "");
      setPayerMobile(initialMobile || "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const cleanReference = reference.trim().replace(/\s+/g, "");
  const referenceOk = cleanReference.length >= MIN_REFERENCE;
  /* Without a paymentId this is the pre-order step, so there is nothing to post
   * to yet - the reference is simply handed back. */
  const collecting = !paymentId;
  const canSubmit = referenceOk && !busy;

  const mobileHint = useMemo(() => {
    const value = payerMobile.trim();
    if (!value) return "";
    const compact = value.replace(/[\s-]/g, "");
    const digits = compact.startsWith("+") ? compact.slice(1) : compact;
    const looksPhone = /^\d+$/.test(digits) && digits.length >= 10 && digits.length <= 15;
    const looksUpi = compact.includes("@") && compact.length >= 5;
    return looksPhone || looksUpi
      ? ""
      : "Enter a 10-digit number or a UPI handle like 9876543210@ybl, or leave it empty.";
  }, [payerMobile]);

  const closeIfAllowed = () => {
    if (blocking || busy) return;
    onClose?.();
  };

  const copyUpiId = async () => {
    if (!upiId) return;
    try {
      await navigator.clipboard.writeText(upiId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      notify.error("Could not copy — note the UPI ID down instead.");
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!referenceOk) {
      setError(
        `Enter the transaction ID / UTR from your UPI app (at least ${MIN_REFERENCE} characters) to continue.`,
      );
      return;
    }
    if (collecting) {
      // Pre-order step: hold the values, close, let checkout place the order.
      setError("");
      onCollected?.({ reference: cleanReference, mobile: payerMobile.trim() });
      onClose?.();
      return;
    }
    setError("");
    setBusy(true);
    try {
      const updated = await paymentService.submitProof(paymentId, {
        transaction_reference: cleanReference,
        payer_mobile: payerMobile.trim(),
      });
      notify.success("Transaction ID saved — the store will confirm your payment.");
      setReference("");
      setPayerMobile("");
      onSubmitted?.(updated);
      if (!blocking) onClose?.();
    } catch (e) {
      setError(e?.message || "Could not save that transaction ID. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={blocking ? undefined : busy ? undefined : onClose}
      title="Pay by UPI, then enter the transaction ID"
    >
      <form onSubmit={submit} className="space-y-3">
        {/* ---- 1. the QR + UPI ID -------------------------------------- */}
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
            {qrUrl ? (
              <img
                src={qrUrl}
                alt={`UPI QR code for ${payeeName || "the store"}`}
                className="h-40 w-40 shrink-0 rounded-xl border border-slate-200 bg-white object-contain p-1.5"
              />
            ) : null}
            <div className="min-w-0 flex-1 text-center sm:text-left">
              <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
                Pay this amount
              </p>
              <p className="text-xl font-extrabold tracking-tight text-slate-900">
                {amount !== undefined && amount !== null ? formatMoney(amount) : "—"}
              </p>
              {payeeName ? (
                <p className="mt-0.5 text-[11px] text-slate-600">to {payeeName}</p>
              ) : null}
              {upiId ? (
                <div className="mt-1.5 flex items-center justify-center gap-2 sm:justify-start">
                  <span className="truncate rounded-md bg-white px-2 py-1 text-[11px] font-bold text-slate-800">
                    {upiId}
                  </span>
                  <button
                    type="button"
                    onClick={copyUpiId}
                    className="shrink-0 rounded-md border border-slate-300 bg-white px-2 py-1 text-[10px] font-bold text-slate-600 hover:bg-slate-50"
                  >
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
              ) : null}
              <p className="mt-1.5 text-[10px] leading-relaxed text-slate-500">
                Scan with GPay, PhonePe, Paytm or your bank app
                {orderNumber ? ` — use ${orderNumber} as the payment note` : ""}.
              </p>
            </div>
          </div>
        </div>

        {/* ---- 2 + 3. the two fields ----------------------------------- */}
        <Input
          label="Transaction ID / UTR"
          required
          name="transaction_reference"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          onBlur={() => setReference((v) => v.trim())}
          placeholder="e.g. 4291000111222333"
          inputMode="numeric"
          maxLength={60}
          autoFocus
        />

        <Input
          label="PhonePe / Google Pay number (optional)"
          name="payer_mobile"
          value={payerMobile}
          onChange={(e) => setPayerMobile(e.target.value)}
          placeholder="Optional — 9876543210 or 9876543210@ybl"
          maxLength={30}
        />
        {mobileHint ? (
          <p className="-mt-1 text-[10px] font-semibold text-amber-700">{mobileHint}</p>
        ) : null}

        <p className="text-[10px] leading-relaxed text-slate-500">
          The transaction ID is under “Payment history” in your UPI app (“UTR” in some banks).
        </p>

        {(blocking || collecting) && !referenceOk ? (
          <p className="rounded-lg bg-sky-50 px-2.5 py-2 text-[11px] font-semibold text-sky-800">
            {collecting
              ? "Enter the transaction ID to place your order."
              : "Enter the transaction ID to continue to your order."}
          </p>
        ) : null}

        {error ? (
          <p className="rounded-lg bg-rose-50 px-2.5 py-2 text-[11px] font-semibold text-rose-700">
            {error}
          </p>
        ) : null}

        <div className="flex items-center justify-end gap-2 pt-1">
          {blocking ? null : (
            <Button type="button" variant="secondary" onClick={closeIfAllowed} disabled={busy}>
              Not yet
            </Button>
          )}
          <Button type="submit" loading={busy} disabled={!canSubmit}>
            {collecting
              ? "Continue to place order"
              : blocking
                ? "Save & view my order"
                : "Save transaction ID"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
