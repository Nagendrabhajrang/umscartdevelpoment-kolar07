import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { storeService } from "../services/storeService";

/**
 * Store settings + a global refresh counter — the same pattern the admin
 * dashboard uses, so both apps invalidate data the same way.
 *
 * `bumpDataVersion()` after any mutation; CartProvider and WishlistProvider
 * watch `dataVersion` and re-fetch.
 */
const StoreContext = createContext(null);

export function StoreProvider({ children }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dataVersion, setDataVersion] = useState(0);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await storeService.getSettings();
      setSettings(data);
      return data;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const bumpDataVersion = useCallback(() => setDataVersion((v) => v + 1), []);

  const value = useMemo(
    () => ({ settings, loading, dataVersion, refresh, bumpDataVersion }),
    [settings, loading, dataVersion, refresh, bumpDataVersion],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore must be used inside <StoreProvider>");
  return ctx;
}

export default StoreContext;
