import { get, getPaginated, post } from "./api";

export const orderService = {
  /** Validates the cart without committing: totals, charges, issues. */
  preview: (payload) => post("/orders/checkout/preview/", payload),

  /** Round 27: checkout runs for a signed-in customer against their own cart. */
  checkoutOrder: (payload) => post("/orders/checkout/", payload),

  /**
   * Legacy guest checkout kept for any client that still posts delivery details
   * without a session; the storefront no longer uses it.
   */
  guestCheckout: (payload) => post("/orders/checkout/guest/", payload),

  /** Public order lookup: order number + the mobile it was placed with. */
  lookup: (orderNumber, mobileNumber) =>
    get("/orders/lookup/", { order_number: orderNumber, mobile_number: mobileNumber }),


  listMine: (params) => getPaginated("/orders/mine/", params),
  get: (id) => get(`/orders/${id}/`),
  history: (id) => get(`/orders/${id}/history/`),
  /** reason must be one of CancellationReasonEnum. */
  cancel: (id, reason = "customer_request", note) =>
    post(`/orders/${id}/cancel/`, { reason, note }),
  reorder: (id) => post(`/orders/${id}/reorder/`, {}),
};

export default orderService;
