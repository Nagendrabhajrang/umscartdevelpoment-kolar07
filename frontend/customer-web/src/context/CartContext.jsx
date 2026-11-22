import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import { cartService } from "../services/cartService";

import { useStore } from "./StoreContext";
import { useNotification } from "./NotificationContext";
import { useAuth } from "./AuthContext";
import { useCustomer } from "./CustomerContext";
import { resetGuestKey } from "../services/guestCart";

/**
 * Server-owned cart.
 *
 * The backend computes every total, so this context never does arithmetic — it
 * caches the last response and re-fetches after each mutation. A failed request
 * leaves the previous cart in place and surfaces a toast rather than blanking
 * the header badge.
 */
const CartContext = createContext(null);

export function CartProvider({ children }) {
  const { dataVersion, bumpDataVersion } = useStore();
  const { notify } = useNotification();
  /*
   * The cart belongs to whoever is signed in. Round 27: the server merges the
   * guest basket into the account during verify-otp, so once `isAuthenticated`
   * flips the very next refresh already shows the merged cart. Watching the
   * session (and the customer id) is what makes that refresh happen - without
   * it the header badge kept showing the old basket count.
   */
  const { isAuthenticated } = useAuth();
  const { customerId } = useCustomer();


  const [cart, setCart] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyProduct, setBusyProduct] = useState(null);

  const refresh = useCallback(async () => {
    /*
     * Round 23: a cart exists with or without an account. Signed out, the
     * request carries the browser's guest key and the server answers with the
     * guest basket, so the header badge and the cart page work before login.
     */
    try {
      const data = await cartService.getCart();
      setCart(data);
      setError(null);
      return data;
    } catch (e) {
      // An empty cart answers 404 on some endpoints; treat that as "no cart".
      if (e?.status === 404) {
        setCart(null);
        setError(null);
        return null;
      }
      setError(e);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, dataVersion, isAuthenticated, customerId]);

  /*
   * The guest key is retired once the basket belongs to an account.
   *
   * The server already merged it during verify-otp (see
   * auth_service._merge_guest_cart); this only drops the leftover browser key so
   * a later sign-out starts a clean guest basket instead of resurrecting one
   * that has already been folded into the account.
   *
   * Round 32: `isAuthenticated` now only flips after the server confirmed the
   * session cookie (see AuthContext.verifyOtp), so reaching this branch really
   * does mean the merge happened. Before that check, a browser that refused the
   * cookie flipped this flag anyway and threw away the only pointer to the
   * guest basket - which is what emptied the cart on login.
   */
  useEffect(() => {
    /*
     * Round 32: the guest basket is adopted by the server on the first
     * authenticated cart request, so the key must still be readable at request
     * time - retiring it in a separate effect raced the fetch and handed the
     * server a freshly minted, empty key instead. That is why the merge silently
     * matched nothing and the shopper's items vanished.
     *
     * So the refresh is awaited here and the key is dropped only afterwards.
     * `isAuthenticated` itself is set only once the server has confirmed the
     * session cookie (AuthContext.verifyOtp), so a browser that refuses the
     * cookie never reaches this branch and keeps its basket.
     */
    if (!isAuthenticated) return undefined;
    let cancelled = false;
    (async () => {
      await refresh();
      if (!cancelled) resetGuestKey();
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, refresh]);


  const add = useCallback(
    async (product, quantity = 1) => {
      /*
       * Round 23 (this reverses round 21): clicking Add always adds. Signed out
       * the line goes into the browser's guest basket, which is merged into the
       * account on login - so a new visitor can shop before they have an
       * account, and an existing one gets the basket folded into their own cart.
       *
       * Nothing navigates here. The shopper stays exactly where they were;
       * going to /cart or /checkout on an Add click is what annoyed them.
       */
      setBusyProduct(product);
      try {
        await cartService.addItem(product, quantity);
        await refresh();
        bumpDataVersion();
        notify.success("Added to cart");
        return true;
      } catch (e) {
        /*
         * A dead session is not a dead end any more. Drop the stale token, fall
         * back to the guest basket and retry once, so the item still lands.
         */
        if (e?.requiresSignIn || e?.status === 401) {
          try {
            await cartService.addItem(product, quantity);
            await refresh();
            bumpDataVersion();
            notify.success("Added to cart");
            return true;
          } catch (retryError) {
            notify.error(retryError?.message || "Could not add that item");
            return false;
          }
        }
        notify.error(e?.message || "Could not add that item");
        return false;
      } finally {
        setBusyProduct(null);
      }
    },
    [refresh, bumpDataVersion, notify],
  );

  const setQuantity = useCallback(
    async (itemId, quantity) => {
      try {
        if (quantity <= 0) await cartService.removeItem(itemId);
        else await cartService.setQuantity(itemId, quantity);
        await refresh();
        bumpDataVersion();
        return true;
      } catch (e) {
        notify.error(e?.message || "Could not update the cart");
        return false;
      }
    },
    [refresh, bumpDataVersion, notify],
  );

  const remove = useCallback(
    async (itemId) => {
      try {
        await cartService.removeItem(itemId);
        await refresh();
        bumpDataVersion();
        notify.info("Removed from cart");
        return true;
      } catch (e) {
        notify.error(e?.message || "Could not remove that item");
        return false;
      }
    },
    [refresh, bumpDataVersion, notify],
  );

  const clear = useCallback(async () => {
    try {
      await cartService.clearCart();
      await refresh();
      bumpDataVersion();
      return true;
    } catch (e) {
      notify.error(e?.message || "Could not clear the cart");
      return false;
    }
  }, [refresh, bumpDataVersion, notify]);

  const applyCoupon = useCallback(
    async (code) => {
      const result = await cartService.applyCoupon(code);
      await refresh();
      bumpDataVersion();
      return result;
    },
    [refresh, bumpDataVersion],
  );

  const removeCoupon = useCallback(async () => {
    await cartService.removeCoupon();
    await refresh();
    bumpDataVersion();
  }, [refresh, bumpDataVersion]);

  /** How many of this product are already in the cart — powers the red chip. */
  const quantityFor = useCallback(
    (productId) => {
      const item = cart?.items?.find(
        (i) => String(i.product) === String(productId) || String(i.product_id) === String(productId),
      );
      return item ? item.quantity : 0;
    },
    [cart],
  );

  const value = useMemo(
    () => ({
      cart,
      items: cart?.items ?? [],
      itemCount: cart?.item_count ?? 0,
      totalQuantity: cart?.total_quantity ?? 0,
      subtotal: cart?.subtotal ?? "0.00",
      savings: cart?.savings ?? "0.00",
      loading,
      error,
      busyProduct,
      add,
      setQuantity,
      remove,
      clear,
      applyCoupon,
      removeCoupon,
      quantityFor,
      refresh,
    }),
    [
      cart, loading, error, busyProduct, add, setQuantity, remove, clear,
      applyCoupon, removeCoupon, quantityFor, refresh,
    ],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside <CartProvider>");
  return ctx;
}

export default CartContext;
