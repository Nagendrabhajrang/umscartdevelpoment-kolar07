import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";

/**
 * Gate for the pages that belong to an account.
 *
 * Round 27: only checkout and the account pages sit behind this. Browsing,
 * searching and filling a cart stay public, so a guest never meets a login wall
 * until they choose to pay.
 *
 * Two details matter for the cart:
 *
 * 1. `state.from` carries the exact page they were on, so signing in returns
 *    them straight to checkout instead of dumping them on the homepage.
 * 2. `state.reason` lets the login screen say "Login to continue with your
 *    order." for checkout, and nothing for a voluntary Login click.
 *
 * While the stored session is still being confirmed this renders a placeholder
 * rather than redirecting - otherwise a reload would bounce a signed-in
 * customer to /login before their token had even been checked.
 */
export default function RequireAuth({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="container-page py-16">
        <div className="mx-auto flex max-w-md flex-col items-center gap-3">
          <span
            className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600"
            aria-hidden="true"
          />
          <p className="text-sm font-medium text-slate-500">Checking your session…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location,
          reason: location.pathname.startsWith("/checkout") ? "checkout" : undefined,
        }}
      />
    );
  }

  return children;
}
