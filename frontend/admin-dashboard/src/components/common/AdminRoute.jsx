import { Navigate, useLocation } from "react-router-dom";

import { useAdminAuth } from "../../context/AdminAuthContext";

/**
 * Gate for the whole dashboard.
 *
 * While the stored session is being confirmed it shows a spinner instead of
 * redirecting, so a refresh with a valid token does not flash the login screen.
 *
 * The backend also enforces this: every admin API call is authorised against the
 * account's role server-side. This component only decides what to render.
 */
export default function AdminRoute({ children }) {
  const { isAuthenticated, loading } = useAdminAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-slate-100">
        <div className="flex flex-col items-center gap-3">
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
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
