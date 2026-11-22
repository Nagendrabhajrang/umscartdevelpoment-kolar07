import { get, post, del } from "./api";

export const wishlistService = {
  /** Returns the customer's default wishlist, creating it if needed. */
  getWishlist: () => get("/wishlist/"),
  getItems: async () => {
    const data = await get("/wishlist/");
    return data?.items ?? [];
  },
  /** Toggles a product: returns { product_id, is_wishlisted, message } */
  toggle: (product) => post("/wishlist/toggle/", { product }),
  addItem: (wishlist, product) => post("/wishlist/items/", { wishlist, product }),
  removeItem: (itemId) => del(`/wishlist/items/${itemId}/`),
  moveToCart: (itemId, quantity = 1) =>
    post(`/wishlist/items/${itemId}/move-to-cart/`, { quantity }),
};

export default wishlistService;
