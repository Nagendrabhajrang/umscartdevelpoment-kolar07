import { useState } from "react";
import { Link } from "react-router-dom";
import { usePagedList } from "../../hooks";
import { orderService } from "../../services/orderService";
import { OrderStatusBadge, PaymentStatusBadge } from "../../components/common/Badge";
import Pagination from "../../components/common/Pagination";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import Button from "../../components/common/Button";
import Skeleton from "../../components/common/Skeleton";
import { formatMoney, formatDateTime, summariseItems } from "../../utils/format";
import { ORDER_STATUS_LABELS } from "../../utils/constants";

const FILTERS = [
  { value: "", label: "All orders" },
  ...Object.entries(ORDER_STATUS_LABELS).map(([value, label]) => ({ value, label })),
];

/**
 * Order history with status filter.
 *
 * `/orders/mine/` returns a plain array, and its `status` query parameter is not
 * guaranteed to be honoured — so the filter is applied here, once, over the rows
 * the API returned. That keeps "no orders" and "no orders with this status"
 * distinct instead of showing an empty list for both.
 */
export default function OrdersPage() {
  const [status, setStatus] = useState("");
  const list = usePagedList(orderService.listMine, { page_size: 20, ordering: "-created_at" });

  const rows = status ? list.rows.filter((o) => o.status === status) : list.rows;

  return (
    <div className="container-page py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">My orders</h1>
        <p className="mt-1 text-sm text-slate-600">Track deliveries and reorder favourites.</p>
      </header>

      <div className="no-scrollbar mb-4 flex gap-1.5 overflow-x-auto pb-1">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setStatus(f.value)}
            className={`shrink-0 rounded-full px-3.5 py-1.5 text-xs font-bold transition ${
              status === f.value
                ? "bg-brand-600 text-white"
                : "bg-white text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-50"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {list.error ? (
        <ErrorState error={list.error} onRetry={list.reload} title="Orders did not load" />
      ) : list.loading ? (
        <div className="space-y-2.5">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-2xl" />
          ))}
        </div>
      ) : !rows.length ? (
        <EmptyState
          title={status ? `No ${ORDER_STATUS_LABELS[status]?.toLowerCase()} orders` : "No orders yet"}
          description={status ? "Try another filter." : "Your placed orders will appear here."}
          action={<Button as={Link} to="/products" size="lg">Start shopping</Button>}
        />
      ) : (
        <ul className="space-y-2.5">
          {rows.map((o) => (
            <li key={o.id}>
              <Link
                to={`/orders/${o.id}`}
                className="block rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-brand-300 hover:shadow-card"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-extrabold text-slate-900">{o.order_number}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500">{formatDateTime(o.created_at)}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <OrderStatusBadge status={o.status} />
                    <PaymentStatusBadge status={o.payment_status} />
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap items-end justify-between gap-2 border-t border-slate-100 pt-3">
                  <div className="min-w-0">
                    <p className="truncate text-xs text-slate-600">{summariseItems(o.items)}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      {o.item_count} item{o.item_count === 1 ? "" : "s"}
                      {o.delivery_city ? ` · ${o.delivery_city}` : ""}
                    </p>
                  </div>
                  <p className="text-base font-extrabold text-slate-900">{formatMoney(o.grand_total)}</p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <Pagination page={list.page} pageCount={list.pageCount} onChange={list.setPage} className="mt-6" />
    </div>
  );
}
