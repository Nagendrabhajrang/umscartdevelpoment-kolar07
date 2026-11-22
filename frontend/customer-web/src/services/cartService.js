import { get, post, patch, del } from "./api";
import { getGuestKey } from "./guestCart";

/** Server-side cart. The backend owns totals; never compute money here. */
export const cartService = {
  getCart: () => get("/cart/"),
  clearCart: () => del("/cart/"),

  addItem: (product, quantity = 1, notes = "") =>
    post("/cart/items/", { product, quantity, notes: notes || undefined }),

  updateItem: (itemId, payload) => patch(`/cart/items/${itemId}/`, payload),
  setQuantity: (itemId, quantity) =>
    patch(`/cart/items/${itemId}/`, { quantity }),
  removeItem: (itemId) => del(`/cart/items/${itemId}/`),
  increment: (itemId) => post(`/cart/items/${itemId}/increment/`, {}),
  decrement: (itemId) => post(`/cart/items/${itemId}/decrement/`, {}),

  getSummary: () => get("/cart/summary/"),

  applyCoupon: (code) => post("/cart/coupon/", { code }),
  removeCoupon: () => del("/cart/coupon/"),

  /**
   * Fold the signed-out basket into the signed-in account's cart.
   * The server marks the guest basket merged, so calling this twice is safe.
   */
  mergeGuestCart: () =>
    post("/cart/merge/", {}, { headers: { "X-Guest-Cart": getGuestKey() } }),
};

export default cartService;
