import { get, postMultipart } from "./api";

/**
 * UPI payments (customer side).
 *
 * The storefront never touches money: it shows the store's UPI ID and QR, then
 * tells the API that the customer says they have paid. An admin checks the bank
 * statement in the console and approves or rejects it.
 *
 *   GET  /payments/{id}/upi-details/   -> what to show on screen
 *   POST /payments/{id}/submit-proof/  -> transaction reference + screenshot
 */
export const paymentService = {
  upiDetails: (paymentId) => get(`/payments/${paymentId}/upi-details/`),

  /**
   * `fields` is { transaction_reference, payer_name?, upi_id?, notes?, proof? }
   * and is sent as multipart because `proof` may be a screenshot file.
   */
  submitProof: (paymentId, fields) =>
    postMultipart(`/payments/${paymentId}/submit-proof/`, fields),
};

/**
 * The `upi://pay` intent every Indian UPI app understands. The backend renders
 * the same string into the store QR; building it here lets the "Open in UPI
 * app" button work on a phone without a round trip.
 */
export function upiIntent({ upiId, payeeName, amount, note }) {
  if (!upiId) return null;
  const params = [`pa=${encodeURIComponent(upiId.trim())}`];
  if (payeeName) params.push(`pn=${encodeURIComponent(payeeName.trim())}`);
  if (amount !== undefined && amount !== null && amount !== "") {
    params.push(`am=${Number(amount).toFixed(2)}`);
  }
  params.push("cu=INR");
  if (note) params.push(`tn=${encodeURIComponent(String(note).slice(0, 50))}`);
  return `upi://pay?${params.join("&")}`;
}

export default paymentService;
