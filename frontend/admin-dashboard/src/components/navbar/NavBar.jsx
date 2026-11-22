import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Menu, ExternalLink, Bell, RefreshCw, Search, LogOut, ChevronDown, KeyRound } from "lucide-react";
import { useStore } from "../../context/StoreContext";
import { useAdminAuth } from "../../context/AdminAuthContext";

/**
 * Top bar: mobile menu toggle, data refresh, API docs and the signed-in
 * administrator's account menu (change password, sign out).
 */
export default function NavBar({ onMenuClick }) {
  const { refresh, bumpDataVersion, loading } = useStore();
  const { displayName, username, email, signOut } = useAdminAuth();
  const navigate = useNavigate();
  const [spinning, setSpinning] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const menuRef = useRef(null);

  // Close the menu on an outside click or Escape - a sticky dropdown that only
  // closes on a second tap feels broken.
  useEffect(() => {
    if (!accountOpen) return undefined;
    const onDown = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) setAccountOpen(false);
    };
    const onKey = (event) => {
      if (event.key === "Escape") setAccountOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [accountOpen]);

  const handleSignOut = async () => {
    setAccountOpen(false);
    await signOut();
    navigate("/login", { replace: true });
  };

  const initial = (displayName || "A").trim().charAt(0).toUpperCase();

  const reloadAll = async () => {
    setSpinning(true);
    await refresh();
    bumpDataVersion();
    setTimeout(() => setSpinning(false), 500);
  };

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-slate-200 bg-white px-3 sm:px-4">
      <button type="button" onClick={onMenuClick} aria-label="Open navigation"
        className="rounded-lg p-2 text-slate-600 transition hover:bg-slate-100 lg:hidden">
        <Menu className="h-5 w-5" aria-hidden="true" />
      </button>

      <div className="hidden items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs text-slate-500 sm:flex">
        <Search className="h-3.5 w-3.5" aria-hidden="true" />
        <kbd className="font-sans">Ctrl</kbd><span>+</span><kbd className="font-sans">K</kbd>
        <span className="ml-1 text-slate-400">quick search</span>
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        <button type="button" onClick={reloadAll} aria-label="Refresh all data"
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50">
          <RefreshCw className={`h-3.5 w-3.5 ${spinning || loading ? "animate-spin" : ""}`} aria-hidden="true" />
          <span className="hidden sm:inline">Refresh</span>
        </button>

        <Link to="/orders?status=pending" aria-label="Pending orders"
          className="relative rounded-lg border border-slate-200 p-1.5 text-slate-600 transition hover:bg-slate-50">
          <Bell className="h-4 w-4" aria-hidden="true" />
        </Link>

        <Link to="http://127.0.0.1:8000/api/docs/" target="_blank" rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50">
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">API docs</span>
        </Link>

        {/* Account menu */}
        <div className="relative ml-1" ref={menuRef}>
          <button
            type="button"
            onClick={() => setAccountOpen((v) => !v)}
            aria-expanded={accountOpen}
            aria-haspopup="menu"
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 py-1 pl-1 pr-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <span className="grid h-6 w-6 place-items-center rounded-md bg-brand-600 text-[11px] font-bold text-white">
              {initial}
            </span>
            <span className="hidden max-w-24 truncate sm:inline">{displayName}</span>
            <ChevronDown className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
          </button>

          {accountOpen ? (
            <div
              role="menu"
              className="absolute right-0 top-11 z-30 w-60 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
            >
              <div className="px-3 py-2">
                <p className="truncate text-sm font-bold text-slate-900">{displayName}</p>
                <p className="truncate text-[11px] text-slate-500">{email || username}</p>
              </div>
              <div className="my-1 h-px bg-slate-100" />
              <Link
                to="/settings?tab=security"
                role="menuitem"
                onClick={() => setAccountOpen(false)}
                className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                <KeyRound className="h-4 w-4 text-slate-400" aria-hidden="true" />
                Change password
              </Link>
              <button
                type="button"
                role="menuitem"
                onClick={handleSignOut}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-rose-600 hover:bg-rose-50"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
                Sign out
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
