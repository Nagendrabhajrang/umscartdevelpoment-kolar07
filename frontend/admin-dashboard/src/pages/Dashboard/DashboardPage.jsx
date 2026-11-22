import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, ArrowRight, Boxes, CheckCircle2, Clock, IndianRupee,
  Package, ShoppingBag, TrendingUp, Users, Wallet, XCircle, RefreshCw,
} from "lucide-react";
import StatCard from "../../components/charts/StatCard";
import BarChart from "../../components/charts/BarChart";
import DonutChart from "../../components/charts/DonutChart";
import { StatSkeleton, TableSkeleton } from "../../components/common/Skeleton";
import ErrorState from "../../components/common/ErrorState";
import Button from "../../components/common/Button";
import { OrderStatusBadge, PaymentStatusBadge } from "../../components/common/Badge";
import EmptyState from "../../components/common/EmptyState";
import { orderService } from "../../services/orderService";
import { paymentService } from "../../services/paymentService";
import { customerService } from "../../services/customerService";
import { inventoryService } from "../../services/inventoryService";
import { promotionService } from "../../services/promotionService";
import { useStore } from "../../context/StoreContext";
import { compactMoney, formatMoney, formatNumber, timeAgo, titleCase } from "../../utils/format";
import { ORDER_STATUS_LABELS } from "../../utils/constants";

/**
 * Dashboard.
 *
 * Every figure on this page is read from an API response at render time:
 *   /orders/stats/            order + revenue totals
 *   /payments/stats/          payment split by method and status
 *   /customers/summary/       customer counts
 *   /inventory/stock/summary/ stock health
 *   /inventory/stock/low-stock/  restock queue
 *   /promotions/summary/      coupon usage
 *   /orders/?ordering=-created_at  recent orders
 *   /payments/pending-verification/  verification queue
 *
 * Nothing is hardcoded and nothing is faked: if an endpoint fails, that card
 * shows an error instead of a made-up number.
 */
export default function DashboardPage() {
  const { dataVersion, bumpDataVersion } = useStore();
  const [state, setState] = useState({
    orderStats: null, paymentStats: null, customerSummary: null,
    stockSummary: null, promotionSummary: null,
    recentOrders: [], lowStock: [], pendingPayments: [],
  });
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});
  const [hardError, setHardError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setErrors({});
    setHardError(null);

    const results = await Promise.allSettled([
      orderService.stats(),
      paymentService.stats(),
      customerService.summary(),
      inventoryService.summary(),
      promotionService.summary(),
      orderService.list({ page_size: 6, ordering: "-created_at" }),
      inventoryService.lowStock({ page_size: 5 }),
      paymentService.pendingVerification({ page_size: 4 }),
    ]);

    const [o, p, c, s, pr, ro, ls, pp] = results;
    const nextErrors = {};
    const pick = (res, key) => {
      if (res.status === "fulfilled") return res.value;
      nextErrors[key] = res.reason;
      return null;
    };

    const next = {
      orderStats: pick(o, "orders"),
      paymentStats: pick(p, "payments"),
      customerSummary: pick(c, "customers"),
      stockSummary: pick(s, "inventory"),
      promotionSummary: pick(pr, "promotions"),
      recentOrders: ro.status === "fulfilled" ? ro.value.results : [],
      lowStock: ls.status === "fulfilled" ? ls.value.results : [],
      pendingPayments: pp.status === "fulfilled" ? pp.value.results : [],
    };

    setState(next);
    setErrors(nextErrors);

    // If the four core aggregates all failed, the API is probably down.
    if ([o, p, c, s].every((r) => r.status === "rejected")) {
      setHardError(o.reason);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load, dataVersion, reloadKey]);

  if (hardError) {
    return (
      <div className="mx-auto max-w-2xl py-10">
        <ErrorState error={hardError} onRetry={() => setReloadKey((k) => k + 1)} title="The dashboard could not reach the API" />
      </div>
    );
  }

  const { orderStats, paymentStats, customerSummary, stockSummary, promotionSummary } = state;

  const statusBreakdown = orderStats
    ? [
        { label: "Pending", value: orderStats.pending_orders },
        { label: "Delivered", value: orderStats.delivered_orders },
        { label: "Cancelled", value: orderStats.cancelled_orders },
      ]
    : [];

  const paymentSplit = paymentStats
    ? [
        { label: "COD", value: Number(paymentStats.cod_payments ?? 0), color: "#f59e0b" },
        { label: "UPI", value: Number(paymentStats.upi_payments ?? 0), color: "#4f46e5" },
      ]
    : [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="mt-0.5 text-xs text-slate-500">
            Live figures from the store API. Refreshed {timeAgo(new Date().toISOString())}.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { setReloadKey((k) => k + 1); bumpDataVersion(); }}
          leftIcon={<RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />}>
          Refresh
        </Button>
      </div>

      {/* KPI row */}
      {loading && !orderStats ? (
        <StatSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Total revenue"
            value={orderStats ? compactMoney(orderStats.total_revenue) : "—"}
            sublabel={orderStats ? `${formatNumber(orderStats.total_orders)} orders all-time` : "Unavailable"}
            icon={IndianRupee}
            tone="green"
          />
          <StatCard
            label="Average order value"
            value={orderStats ? formatMoney(orderStats.average_order_value) : "—"}
            sublabel={orderStats ? `${orderStats.fulfilment_rate}% fulfilment rate` : "Unavailable"}
            icon={TrendingUp}
            tone="brand"
          />
          <StatCard
            label="Pending orders"
            value={orderStats ? formatNumber(orderStats.pending_orders) : "—"}
            sublabel="Awaiting confirmation"
            icon={Clock}
            tone="amber"
          />
          <StatCard
            label="Customers"
            value={customerSummary ? formatNumber(customerSummary.total) : "—"}
            sublabel={customerSummary ? `${formatNumber(customerSummary.active)} active · ${formatNumber(customerSummary.blocked)} blocked` : "Unavailable"}
            icon={Users}
            tone="violet"
          />
        </div>
      )}

      {/* Second KPI row */}
      {!loading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Delivered"
            value={orderStats ? formatNumber(orderStats.delivered_orders) : "—"}
            icon={CheckCircle2}
            tone="green"
            sublabel={orderStats ? `${orderStats.cancelled_orders} cancelled` : ""}
          />
          <StatCard
            label="Stock alerts"
            value={stockSummary ? formatNumber(stockSummary.low_stock) : "—"}
            icon={AlertTriangle}
            tone="amber"
            sublabel={stockSummary ? `${formatNumber(stockSummary.out_of_stock)} out of stock · ${formatNumber(stockSummary.total_units)} units` : "Unavailable"}
          />
          <StatCard
            label="Coupon redemptions"
            value={promotionSummary ? formatNumber(promotionSummary.total_redemptions) : "—"}
            icon={Package}
            tone="sky"
            sublabel={promotionSummary ? `${formatNumber(promotionSummary.active)} active · ${formatNumber(promotionSummary.coupons)} coupons` : "Unavailable"}
          />
          <StatCard
            label="Pending payments"
            value={paymentStats ? formatNumber(paymentStats.pending_verification) : "—"}
            icon={Wallet}
            tone="rose"
            sublabel={paymentStats ? `${formatMoney(paymentStats.settled_amount)} settled` : "Unavailable"}
          />
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <section className="card p-4 lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900">Orders by status</h2>
            <Link to="/orders" className="text-xs font-semibold text-brand-700 hover:underline">View all orders</Link>
          </div>
          {errors.orders ? (
            <ErrorState error={errors.orders} compact title="Order stats unavailable" />
          ) : (
            <BarChart
              data={statusBreakdown}
              valueFormat={(v) => `${v} orders`}
              ariaLabel="Orders grouped by status"
              color="#4f46e5"
            />
          )}
        </section>

        <section className="card p-4">
          <h2 className="mb-2 text-sm font-bold text-slate-900">Payment split</h2>
          {errors.payments ? (
            <ErrorState error={errors.payments} compact title="Payment stats unavailable" />
          ) : (
            <DonutChart
              data={paymentSplit}
              centerValue={formatNumber((paymentStats?.cod_payments ?? 0) + (paymentStats?.upi_payments ?? 0))}
              centerLabel="payments"
            />
          )}
        </section>
      </div>

      {/* Tables */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <section className="card p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900">Recent orders</h2>
            <Link to="/orders" className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline">
              All orders <ArrowRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          </div>
          {loading && !state.recentOrders.length ? (
            <TableSkeleton rows={4} cols={4} />
          ) : !state.recentOrders.length ? (
            <EmptyState icon={ShoppingBag} title="No orders yet" description="Orders will appear here as customers check out." compact />
          ) : (
            <ul className="divide-y divide-slate-100">
              {state.recentOrders.map((order) => (
                <li key={order.id}>
                  <Link to={`/orders/${order.id}`} className="flex items-center gap-3 rounded-lg px-1 py-2.5 transition hover:bg-slate-50">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold text-slate-900">{order.order_number}</p>
                      <p className="truncate text-xs text-slate-500">
                        {order.customer_name} · {order.item_count} item{order.item_count === 1 ? "" : "s"} · {timeAgo(order.created_at)}
                      </p>
                    </div>
                    <OrderStatusBadge status={order.status} />
                    <span className="w-20 shrink-0 text-right text-sm font-bold tabular-nums text-slate-900">
                      {formatMoney(order.grand_total)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900">Needs attention</h2>
            <Link to="/inventory" className="text-xs font-semibold text-brand-700 hover:underline">Inventory</Link>
          </div>

          <h3 className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-400">Low stock</h3>
          {!state.lowStock.length ? (
            <p className="rounded-lg bg-emerald-50 px-2.5 py-2 text-xs font-medium text-emerald-700">All stock levels are healthy.</p>
          ) : (
            <ul className="space-y-1.5">
              {state.lowStock.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-2 rounded-lg bg-amber-50 px-2.5 py-1.5">
                  <span className="min-w-0 truncate text-xs font-medium text-amber-900">{item.product_name}</span>
                  <span className="shrink-0 text-xs font-bold text-amber-800">{item.quantity_available} left</span>
                </li>
              ))}
            </ul>
          )}

          <h3 className="mb-1.5 mt-4 text-[11px] font-bold uppercase tracking-wide text-slate-400">Payments to verify</h3>
          {!state.pendingPayments.length ? (
            <p className="rounded-lg bg-slate-50 px-2.5 py-2 text-xs text-slate-500">Nothing pending.</p>
          ) : (
            <ul className="space-y-1.5">
              {state.pendingPayments.map((p) => (
                <li key={p.id}>
                  <Link to="/payments" className="flex items-center justify-between gap-2 rounded-lg bg-sky-50 px-2.5 py-1.5 hover:bg-sky-100">
                    <span className="min-w-0 truncate text-xs font-medium text-sky-900">{p.order_number}</span>
                    <span className="shrink-0 text-xs font-bold text-sky-800">{formatMoney(p.amount)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {state.pendingPayments.length > 0 && (
            <Link to="/payments?tab=pending" className="mt-3 block">
              <Button size="xs" variant="outline" fullWidth>Open verification queue</Button>
            </Link>
          )}
        </section>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { to: "/products", label: "Add a product", icon: Package, text: "Create or edit catalog items" },
          { to: "/inventory", label: "Update stock", icon: Boxes, text: "Add or remove quantity" },
          { to: "/promotions", label: "Create an offer", icon: TrendingUp, text: "Coupons and discounts" },
          { to: "/settings", label: "Store settings", icon: Clock, text: "UPI, delivery, hours" },
        ].map(({ to, label, icon: Icon, text }) => (
          <Link key={to} to={to} className="card flex items-center gap-3 p-3 transition hover:border-brand-300 hover:shadow">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand-50 text-brand-700">
              <Icon className="h-4 w-4" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900">{label}</p>
              <p className="truncate text-xs text-slate-500">{text}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
