import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import Logo from "../common/Logo";
import SearchBar from "../common/SearchBar";
import { useCart } from "../../context/CartContext";
import { useAuth } from "../../context/AuthContext";
import { useCustomer } from "../../context/CustomerContext";
import { useWishlist } from "../../context/WishlistContext";
import { useStore } from "../../context/StoreContext";
import { initials } from "../../utils/format";

/**
 * Sticky header.
 *
 * The cart badge is red (Amazon/JioMart convention) and is hidden at zero so an
 * empty cart does not shout. Nothing here animates on navigation.
 *
 * Round 27: the header shows Login for a guest and My Account for a signed-in
 * customer, which is the pattern every large store uses - browsing stays open,
 * and the only thing behind the button is the customer's own data.
 */
export default function NavBar() {
  const { itemCount } = useCart();
  const { count: wishCount } = useWishlist();
  const { isAuthenticated, displayName, mobileNumber, signOut } = useAuth();
  const { profile } = useCustomer();
  const { settings } = useStore();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);

  /*
   * The button shows the customer's first name once we know it. A brand-new
   * account has only a verified mobile, and a wrapped 13-character number looks
   * broken in a 96px slot, so that case reads "My account" - the full number is
   * in the dropdown either way.
   */
  const rawName = profile?.full_name || displayName || "";
  const name = /^[+]?\d[\d\s-]*$/.test(rawName.trim()) ? "" : rawName.trim();
  const accountLabel = name ? name.split(" ")[0] : "My account";

  const handleSignOut = async () => {
    setAccountOpen(false);
    await signOut();
    navigate("/", { replace: true });
  };

  const delivery = settings?.delivery_eta_minutes;

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="container-page flex h-16 min-w-0 items-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="Open menu"
          aria-expanded={menuOpen}
          className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-slate-600 hover:bg-slate-100 lg:hidden"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
          </svg>
        </button>

        <Logo />

        <div className="mx-auto hidden w-full max-w-md lg:block">
          <SearchBar />
        </div>

        <nav className="ml-auto hidden items-center gap-1 lg:flex" aria-label="Main">
          <TopLink to="/">Home</TopLink>
          <TopLink to="/categories">Categories</TopLink>
          <TopLink to="/products">Products</TopLink>
          <TopLink to="/orders">Orders</TopLink>
          <TopLink to="/help">Help</TopLink>
        </nav>

        <div className="ml-auto flex min-w-0 shrink items-center justify-end gap-0.5 sm:gap-1 lg:ml-2 lg:shrink-0">
          {isAuthenticated ? (
            <IconLink to="/wishlist" label="Wishlist" badge={wishCount} tone="rose">
              <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8Z" strokeLinejoin="round" />
            </IconLink>
          ) : null}

          {/* Cart — red count badge */}
          <IconLink to="/cart" label="Cart" badge={itemCount} tone="red">
            <circle cx="9" cy="20" r="1.5" />
            <circle cx="18" cy="20" r="1.5" />
            <path d="M2 3h2.2l2.3 12h11.2l2.3-8H6" strokeLinecap="round" strokeLinejoin="round" />
          </IconLink>

          {/* Account: Login for a guest, My Account once signed in. */}
          <div className="relative ml-1 shrink-0">
            {isAuthenticated ? (
              <>
                <button
                  type="button"
                  onClick={() => setAccountOpen((v) => !v)}
                  aria-expanded={accountOpen}
                  aria-haspopup="menu"
                  className="flex h-9 items-center gap-1.5 rounded-full bg-slate-100 pl-1 pr-2.5 text-sm font-semibold text-slate-800 hover:bg-slate-200"
                >
                  <span className="grid h-7 w-7 place-items-center rounded-full bg-brand-600 text-[11px] font-bold text-white">
                    {initials(name || mobileNumber || "U")}
                  </span>
                  <span className="hidden max-w-24 truncate sm:inline">{accountLabel}</span>
                </button>

                {accountOpen ? (
                  <>
                    <button
                      type="button"
                      aria-hidden="true"
                      tabIndex={-1}
                      className="fixed inset-0 z-10 cursor-default"
                      onClick={() => setAccountOpen(false)}
                    />
                    <div
                      role="menu"
                      className="absolute right-0 top-11 z-20 w-56 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
                    >
                      <p className="truncate px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-slate-400">
                        {mobileNumber || "Signed in"}
                      </p>
                      <Link to="/profile" role="menuitem" onClick={() => setAccountOpen(false)}
                        className="block px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                        My profile
                      </Link>
                      <Link to="/orders" role="menuitem" onClick={() => setAccountOpen(false)}
                        className="block px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                        My orders
                      </Link>
                      <Link to="/addresses" role="menuitem" onClick={() => setAccountOpen(false)}
                        className="block px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                        Saved addresses
                      </Link>
                      <div className="my-1 h-px bg-slate-100" />
                      <button type="button" role="menuitem" onClick={handleSignOut}
                        className="block w-full px-3 py-2 text-left text-sm font-semibold text-rose-600 hover:bg-rose-50">
                        Logout
                      </button>
                    </div>
                  </>
                ) : null}
              </>
            ) : (
              <Link
                to="/login"
                state={{ from: { pathname: "/" } }}
                className="flex h-9 items-center gap-1.5 rounded-full bg-brand-600 px-3.5 text-sm font-bold text-white hover:bg-brand-700"
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <circle cx="12" cy="8" r="3.5" />
                  <path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6" strokeLinecap="round" />
                </svg>
                Login
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Mobile search */}
      <div className="container-page pb-2.5 lg:hidden">
        <SearchBar />
      </div>

      {/* Mobile nav drawer */}
      {menuOpen ? (
        <nav className="border-t border-slate-200 bg-white px-4 py-2 lg:hidden" aria-label="Mobile">
          {[
            ["/", "Home"],
            ["/categories", "Categories"],
            ["/products", "Products"],
            ...(isAuthenticated
              ? [["/orders", "My orders"], ["/wishlist", "Wishlist"]]
              : [["/login", "Login"]]),
            ["/help", "Help"],
          ].map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `block rounded-lg px-2 py-2 text-sm font-semibold ${
                  isActive ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-50"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      ) : null}
    </header>
  );
}

function TopLink({ to, children }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        `rounded-lg px-2.5 py-1.5 text-sm font-semibold transition ${
          isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

/**
 * Icon button with a count bubble. `tone="red"` is the cart — deliberately the
 * loudest thing in the header, matching how Amazon and JioMart signal a
 * non-empty cart.
 */
function IconLink({ to, label, badge = 0, tone = "rose", children }) {
  const colors =
    tone === "red"
      ? "bg-rose-600 ring-white"
      : "bg-rose-500 ring-white";

  return (
    <Link
      to={to}
      aria-label={badge > 0 ? `${label}, ${badge} items` : label}
      className="relative grid h-10 w-10 place-items-center rounded-xl text-slate-700 transition hover:bg-slate-100"
    >
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.9">
        {children}
      </svg>
      {badge > 0 ? (
        <span
          className={`absolute -right-0.5 -top-0.5 grid h-[18px] min-w-[18px] place-items-center rounded-full px-1 text-[10px] font-bold leading-none text-white shadow-sm ring-2 ${colors}`}
          style={{ animation: "badge-pop .3s cubic-bezier(.34,1.56,.64,1)" }}
        >
          {badge > 99 ? "99+" : badge}
        </span>
      ) : null}
    </Link>
  );
}
