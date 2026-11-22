import { get, getPaginated, patch, post } from "./api";

/**
 * Payments: verification queue, approve/reject, COD collection, refunds.
 * NOTE the path is `cod-collected`, not `collect-cod`.
 */
export const paymentService = {
  list: (params) => getPaginated("/payments/", params),
  get: (id) => get(`/payments/${id}/`),
  pendingVerification: (params) => getPaginated("/payments/pending-verification/", params),
  stats: () => get("/payments/stats/"),

  approve: (id, payload = {}) => post(`/payments/${id}/approve/`, payload),
  reject: (id, reason, verified_by) => post(`/payments/${id}/reject/`, { reason, verified_by }),
  markCodCollected: (id, payload = {}) => post(`/payments/${id}/cod-collected/`, payload),
  /** Correct the payer's mobile number / UPI id without touching the status. */
  updateReference: (id, payload = {}) => patch(`/payments/${id}/reference/`, payload),
  refund: (id, payload = {}) => post(`/payments/${id}/refund/`, payload),
  verifications: (id) => getPaginated(`/payments/${id}/verifications/`),

  listRefunds: (params) => getPaginated("/payments/refunds/", params),
};

export default paymentService;
