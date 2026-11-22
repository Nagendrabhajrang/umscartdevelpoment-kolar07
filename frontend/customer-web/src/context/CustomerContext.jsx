import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { useAuth } from "./AuthContext";
import { customerService } from "../services/customerService";
import { addressService } from "../services/addressService";

/**
 * Who is shopping.
 *
 * The identity itself now comes from the authenticated session: `AuthContext`
 * holds the tokens and resolves the account, and this provider fetches the
 * linked commerce `Customer` so the rest of the storefront can use one shape.
 *
 * When nobody is signed in there is no customer - `customerId` is null and the
 * pages that need one are behind `RequireAuth`. The legacy demo switcher is gone;
 * browsing the catalogue anonymously still works because those routes do not
 * ask for a customer.
 */
const CustomerContext = createContext(null);

export function CustomerProvider({ children }) {
  const { user, isAuthenticated, updateProfile } = useAuth();

  const [profile, setProfile] = useState(null);
  const [addresses, setAddresses] = useState([]);
  const [loading, setLoading] = useState(false);

  // The commerce Customer id for the signed-in account, if there is one.
  const customerId = user?.customer_id ?? null;

  const load = useCallback(async () => {
    if (!customerId) {
      setProfile(null);
      setAddresses([]);
      return;
    }
    setLoading(true);
    try {
      const [me, addrs] = await Promise.all([
        customerService.get(customerId).catch(() => null),
        addressService.listMine().catch(() => []),
      ]);
      setProfile(me);
      setAddresses(Array.isArray(addrs) ? addrs : []);
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => {
    load();
  }, [load]);

  // NOTE: deliberately does NOT write the signed-in customer id into the guest
  // storage key. Doing that poisoned anonymous browsing: after signing in and
  // out, the next guest request sent `X-Customer-Id: <their id>`, which either
  // no longer existed ("Customer '72' does not exist") or pointed at someone
  // else's cart. The signed-in identity travels in the bearer token only.

  const defaultAddress = useMemo(
    () => addresses.find((a) => a.is_default) || addresses[0] || null,
    [addresses],
  );

  /**
   * Update the shopper's own profile.
   *
   * The name lives on the commerce `Customer`, so it is written there and then
   * refreshed locally; `AuthContext.updateProfile` handles the account fields.
   */
  const saveProfile = useCallback(
    async (patch) => {
      if (!customerId) throw new Error("Sign in to edit your profile.");
      const updated = await customerService.update(customerId, patch);
      setProfile(updated);
      await updateProfile(patch);
      return updated;
    },
    [customerId, updateProfile],
  );

  const value = useMemo(
    () => ({
      customerId,
      profile,
      addresses,
      defaultAddress,
      loading,
      isAuthenticated,
      refresh: load,
      saveProfile,
      setAddresses,
    }),
    [customerId, profile, addresses, defaultAddress, loading, isAuthenticated, load, saveProfile],
  );

  return <CustomerContext.Provider value={value}>{children}</CustomerContext.Provider>;
}

export function useCustomer() {
  const ctx = useContext(CustomerContext);
  if (!ctx) throw new Error("useCustomer must be used inside <CustomerProvider>");
  return ctx;
}

export default CustomerContext;
