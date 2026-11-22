import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  BarChart3, Boxes, Image, LayoutDashboard, Megaphone, Package,
  Settings, ShoppingBag, Tag, Users, Wallet, Headphones, X, Store,
} from "lucide-react";
import clsx from "clsx";
import { useStore } from "../../context/StoreContext";
import { orderService } from "../../services/orderService";
import { paymentService } from "../../services/paymentService";

/**
 * Primary navigation. Each entry maps to a page that exists; nothing links to
 * a placeholder. The store's open/closed state is shown live from settings.
 */
export const NAV_SECTIONS = [
  {
    title: "Overview",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
      { to: "/orders", label: "Orders", icon: ShoppingBag },
      { to: "/payments", label: "Payments", icon: Wallet },
    ],
  },
  {
    title: "Catalog",
    items: [
      { to: "/products", label: "Products", icon: Package },
      { to: "/categories", label: "Categories", icon: Tag },
      { to: "/inventory", label: "Inventory", icon: Boxes },
    ],
  },
  {
    title: "Customers & marketing",
    items: [
      { to: "/customers", label: "Customers", icon: Users },
      { to: "/promotions", label: "Promotions", icon: Megaphone },
      { to: "/banners", label: "Banners", icon: Image },
    ],
  },
  {
    title: "Operations",
    items: [
      { to: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

/**
 * Circular counter sitting at the right edge of a nav row - the same "bubble"
 * treatment the storefront uses on the cart icon.
 *
 * Plain CSS animation rather than framer-motion: the old `key={count}` +
 * spring version remounted on every polling tick, so the spring kept
 * restarting at scale 0.4 and the badge rendered at 7px instead of 18px.
 */
function SidebarBadge({ count }) {
  if (!count) return null;
  const label = count > 99 ? "99+" : String(count);
  const wide = label.length > 1;
  return (
    <span
      className={`sidebar-badge ml-auto inline-grid shrink-0 place-items-center rounded-full bg-rose-600 font-bold leading-none text-white shadow-sm ring-2 ring-white ${
        wide ? "h-[18px] min-w-[18px] px-1.5 text-[10px]" : "h-[18px] w-[18px] text-[10px]"
      }`}
      aria-label={`${count} needing attention`}
    >
      {label}
    </span>
  );
}

export default function Sidebar({ open, onClose }) {
  const { settings, dataVersion } = useStore();
  const isOpen = settings?.is_store_open !== false;
  const location = useLocation();

  // Live counters for the two queues that need someone's attention: orders
  // waiting to be confirmed and deliveries whose cash is still outstanding.
  const [counts, setCounts] = useState({ orders: 0, payments: 0 });

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [orderStats, paymentStats] = await Promise.all([
          orderService.stats().catch(() => null),
          paymentService.stats().catch(() => null),
        ]);
        if (cancelled) return;
        setCounts({
          // Only genuinely pending rows are counted. Anything confirmed,
          // packed or out for delivery is in flight, not pending, and must
          // not raise a badge.
          orders: orderStats?.pending_orders ?? 0,
          payments: paymentStats?.pending_count ?? 0,
        });
      } catch {
        /* counters are decoration - never break navigation over them */
      }
    };
    load();
    // Also poll, so a customer placing an order shows up without a reload.
    const timer = setInterval(load, 30000);
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => {
      cancelled = true;
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
    // dataVersion bumps after every admin action, so the badge updates the
    // moment a status changes instead of waiting for the next poll.
  }, [location.pathname, dataVersion]);

  const badgeFor = (to) => {
    if (to === "/orders") return counts.orders;
    if (to === "/payments") return counts.payments;
    return 0;
  };

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-30 bg-slate-900/50 lg:hidden" onClick={onClose} aria-hidden="true" />
      )}

      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Dashboard navigation"
      >
        <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-4">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-white">
            <Store className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-extrabold text-slate-900">{settings?.store_name || "UMS Mart"}</p>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Admin console</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close navigation" className="rounded p-1 text-slate-400 hover:bg-slate-100 lg:hidden">
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title} className="mb-3">
              <p className="px-2.5 pb-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">{section.title}</p>
              <ul className="space-y-0.5">
                {section.items.map(({ to, label, icon: Icon, end }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      end={end}
                      onClick={onClose}
                      className={({ isActive }) =>
                        clsx(
                          "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition",
                          isActive
                            ? "bg-brand-50 text-brand-700"
                            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                        )
                      }
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span className="flex-1">{label}</span>
                      <SidebarBadge count={badgeFor(to)} />
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-slate-200 p-3">
          <div className={clsx("flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-semibold", isOpen ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700")}>
            <span className={clsx("h-2 w-2 rounded-full", isOpen ? "bg-emerald-500" : "bg-rose-500")} aria-hidden="true" />
            Store is {isOpen ? "open" : "closed"}
          </div>
        </div>
      </aside>
    </>
  );
}
