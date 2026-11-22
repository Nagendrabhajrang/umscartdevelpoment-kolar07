import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { wishlistService } from "../services/wishlistService";
import { useStore } from "./StoreContext";
import { useNotification } from "./NotificationContext";
import { useAuth } from "./AuthContext";

/** Saved products. Toggling is optimistic — the heart flips immediately. */
const WishlistContext = createContext(null);

export function WishlistProvider({ children }) {
  const { dataVersion } = useStore();
  const { notify } = useNotification();
  // The wishlist belongs to an account. Asking the server for one while signed
  // out only produced a customer_not_found error on every page load.
  const { isAuthenticated } = useAuth();

  const [wishlist, setWishlist] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) {
      setWishlist(null);
      setItems([]);
      setLoading(false);
      return;
    }
    try {
      const data = await wishlistService.getWishlist();
      setWishlist(data);
      setItems(data?.items ?? []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    refresh();
  }, [refresh, dataVersion]);

  const ids = useMemo(
    () => new Set(items.map((i) => i.product ?? i.product_id)),
    [items],
  );

  const has = useCallback((productId) => ids.has(productId), [ids]);

  const toggle = useCallback(
    async (productId) => {
      if (!isAuthenticated) {
        notify.info("Sign in to save items to your wishlist");
        return;
      }
      const wasSaved = ids.has(productId);
      // Optimistic flip; reconciled by the refresh below.
      setItems((list) =>
        wasSaved
          ? list.filter((i) => (i.product ?? i.product_id) !== productId)
          : [...list, { product: productId, product_id: productId }],
      );
      try {
        const result = await wishlistService.toggle(productId);
        await refresh();
        notify.success(result?.message || (wasSaved ? "Removed from wishlist" : "Saved to wishlist"));
        return result;
      } catch (e) {
        await refresh();
        notify.error(e?.message || "Could not update your wishlist");
        return null;
      }
    },
    [ids, refresh, notify],
  );

  const remove = useCallback(
    async (itemId) => {
      try {
        await wishlistService.removeItem(itemId);
        await refresh();
        notify.info("Removed from wishlist");
      } catch (e) {
        notify.error(e?.message || "Could not remove that item");
      }
    },
    [refresh, notify],
  );

  const value = useMemo(
    () => ({ wishlist, items, ids, count: items.length, loading, has, toggle, remove, refresh }),
    [wishlist, items, ids, loading, has, toggle, remove, refresh],
  );

  return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>;
}

export function useWishlist() {
  const ctx = useContext(WishlistContext);
  if (!ctx) throw new Error("useWishlist must be used inside <WishlistProvider>");
  return ctx;
}

export default WishlistContext;
