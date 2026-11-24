import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Eye, Truck, Wallet, XCircle } from "lucide-react";
import Button from "../../components/common/Button";
import Select from "../../components/common/Select";
import Pagination from "../../components/common/Pagination";
import DataTable from "../../components/tables/DataTable";
import TableToolbar from "../../components/tables/TableToolbar";
import { OrderStatusBadge } from "../../components/common/Badge";
import ErrorState from "../../components/common/ErrorState";
import { useListPage } from "../../hooks/useListPage";
import { useStore } from "../../context/StoreContext";
import { useNotification } from "../../context/NotificationContext";
import { orderService } from "../../services/orderService";
import { formatMoney, formatDateTime, titleCase, downloadCsv } from "../../utils/format";
import { ORDER_STATUS_LABELS } from "../../utils/constants";

const STATUS_FILTERS = [
  { value: "", label: "All statuses" },
  ...Object.entries(ORDER_STATUS_LABELS).map(([value, label]) => ({ value, label })),
];

const PAYMENT_METHODS = [
  { value: "", label: "Any method" },
  { value: "cod", label: "Cash on delivery" },
  { value: "upi", label: "UPI" },
];

/**
 * Status summary cards.
 *
 * One card per pipeline stage, in fulfilment order. Each card doubles as the
 * status filter: clicking it selects that status in the table below, clicking
 * the active one clears the filter. Counts come from `/orders/?status=…`
 * with `page_size=1` — the response's `count` is the number, so the payload
 * stays tiny however many orders exist.
 */
const STATUS_CARDS = [
  { key: "pending", label: "Pending", tone: "border-amber-200 bg-amber-50 text-amber-900", chip: "bg-amber-500" },
  { key: "packed", label: "Packed", tone: "border-teal-200 bg-teal-50 text-teal-900", chip: "bg-teal-500" },
  { key: "out_for_delivery", label: "Out for delivery", tone: "border-violet-200 bg-violet-50 text-violet-900", chip: "bg-violet-500" },
  { key: "delivered", label: "Delivered", tone: "border-emerald-200 bg-emerald-50 text-emerald-900", chip: "bg-emerald-500" },
  { key: "cancelled", label: "Cancelled", tone: "border-rose-200 bg-rose-50 text-rose-900", chip: "bg-rose-500" },
  { key: "returned", label: "Returned", tone: "border-orange-200 bg-orange-50 text-orange-900", chip: "bg-orange-500" },
  { key: "refunded", label: "Refunded", tone: "border-slate-200 bg-slate-50 text-slate-900", chip: "bg-slate-500" },
];

/**
 * Order operations. The backend owns the status machine - each row only shows
 * the actions the API says are legal for that order (`next_statuses`).
 */
export default function OrdersPage() {
  const [params, setParams] = useSearchParams();
  const { dataVersion, bumpDataVersion } = useStore();
  const { notify } = useNotification();

  const list = useListPage(orderService.list, { page_size: 20, ordering: "-created_at", status: params.get("status") || "" });
  const [busyId, setBusyId] = useState(null);
  const [counts, setCounts] = useState({});
  const [countsLoading, setCountsLoading] = useState(true);

  /** Fetch every status count in parallel; a failed card just shows a dash. */
  const loadCounts = useCallback(async () => {
    setCountsLoading(true);
    const results = await Promise.all(
      STATUS_CARDS.map((c) =>
        orderService
          .list({ status: c.key, page_size: 1 })
          .then((page) => [c.key, page?.count ?? 0])
          .catch(() => [c.key, null]),
      ),
    );
    setCounts(Object.fromEntries(results));
    setCountsLoading(false);
  }, []);

  useEffect(() => { list.reload(); loadCounts(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [dataVersion]);

  /** Clicking a card filters the table to that status; clicking again clears it. */
  const selectStatus = (key) => {
    const next = list.filters.status === key ? "" : key;
    list.setFilter("status", next);
    setParams(next ? { status: next } : {}, { replace: true });
  };

  const act = async (order, action, label) => {
    setBusyId(order.id);
    try {
      if (action === "deliver") await orderService.markDelivered(order.id);
      if (action === "cancel") await orderService.updateStatus(order.id, "cancelled", "Cancelled from admin");
      notify.success(label);
      list.reload();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "That status change was rejected.");
    } finally {
      setBusyId(null);
    }
  };

  const columns = [
    {
      key: "order_number",
      header: "Order",
      sortable: true,
      render: (r) => (
        <Link to={`/orders/${r.id}`} className="group block">
          <p className="font-bold text-slate-900 group-hover:text-brand-700">{r.order_number}</p>
          <p className="mt-0.5 text-[11px] text-slate-500">{formatDateTime(r.created_at)}</p>
        </Link>
      ),
    },
    {
      key: "customer_name",
      header: "Customer",
      sortable: true,
      render: (r) => (
        <div className="space-y-0.5">
          <p className="text-xs font-semibold text-slate-800">{r.customer_name}</p>
          <p className="text-[11px] text-slate-500">{r.customer_mobile || "—"}</p>
        </div>
      ),
    },
    {
      key: "grand_total",
      header: "Amount",
      sortable: true,
      align: "right",
      render: (r) => <span className="font-bold text-slate-900">{formatMoney(r.grand_total)}</span>,
    },
    {
      key: "payment_method",
      header: "Payment",
      // Cash on delivery is the only method, so the status pill ("cod due",
      // "cod collected") is just noise next to the method name. Show the
      // method alone.
      render: (r) => (
        <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">
          {r.payment_method_display || r.payment_method}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      render: (r) => <OrderStatusBadge status={r.status} />,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => {
        const next = row.next_statuses || [];
        // Delivery is only offered once the money is in: cash recorded for COD,
        // payment_status=paid otherwise. When unpaid the action is HIDDEN, not
        // disabled — a greyed-out icon still takes up space in the row and reads
        // as clutter next to the status pill.
        // Same rule as the backend: only paid / cash-collected counts.
        const isPaid = ["paid", "cod_collected"].includes(row.payment_status);
        const canDeliver = next.includes("delivered") && isPaid;
        const busy = busyId === row.id;
        return (
          <div className="flex items-center justify-end gap-1">
            {/* At the delivery window it is one or the other, never both:
                cash outstanding -> a Collect cash link into Payments;
                cash recorded    -> Mark delivered. */}
            {next.includes("delivered") && !isPaid && (
              <Link
                to={`/payments?collect=${row.payment_id ?? ""}&from=${row.id}`}
                title="Collect cash — opens this order's payment"
                className="rounded p-1.5 text-amber-600 hover:bg-amber-50"
              >
                <Wallet className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">Collect cash for {row.order_number}</span>
              </Link>
            )}
            {canDeliver && (
              <button type="button" disabled={busy}
                onClick={() => act(row, "deliver", `${row.order_number} marked delivered`)}
                title="Mark delivered"
                className="rounded p-1.5 text-sky-600 hover:bg-sky-50 disabled:opacity-40">
                <Truck className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">Mark {row.order_number} delivered</span>
              </button>
            )}
            {row.status === "pending" && (
              <button type="button" disabled={busy} onClick={() => act(row, "cancel", `${row.order_number} cancelled`)}
                title="Cancel order"
                className="rounded p-1.5 text-rose-600 hover:bg-rose-50 disabled:opacity-40">
                <XCircle className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">Cancel {row.order_number}</span>
              </button>
            )}
            <Link to={`/orders/${row.id}`} title="View order details"
              className="rounded p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800">
              <Eye className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">View {row.order_number}</span>
            </Link>
          </div>
        );
      },
    },
  ];

  return (
    <div>
      <div className="mb-3">
        <h1 className="page-title">Orders</h1>
        <p className="mt-0.5 text-xs text-slate-500">Move orders through the fulfilment flow. Only legal transitions are offered.</p>
      </div>

      <div className="mb-3">
        <div className="flex items-center justify-between">
          <h2 className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
            Orders by status
          </h2>
          {list.filters.status ? (
            <button
              type="button"
              onClick={() => { list.setFilter("status", ""); setParams({}, { replace: true }); }}
              className="text-[11px] font-semibold text-brand-700 hover:underline"
            >
              Clear filter
            </button>
          ) : null}
        </div>

        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
          {STATUS_CARDS.map((c) => {
            const active = list.filters.status === c.key;
            const value = counts[c.key];
            return (
              <button
                key={c.key}
                type="button"
                onClick={() => selectStatus(c.key)}
                aria-pressed={active}
                aria-label={`Show ${c.label} orders${value ? ` (${value})` : ""}`}
                className={`relative rounded-xl border p-3 text-left transition hover:shadow-sm ${c.tone} ${
                  active ? "ring-2 ring-brand-500 ring-offset-1" : ""
                }`}
              >
                <span className={`absolute right-2.5 top-2.5 h-1.5 w-1.5 rounded-full ${c.chip}`} />
                <p className="text-[10px] font-bold uppercase tracking-wide opacity-70">
                  {c.label}
                </p>
                <p className="mt-1 text-xl font-extrabold tabular-nums leading-none">
                  {countsLoading && value === undefined ? "—" : value === null ? "—" : value ?? 0}
                </p>
                <p className="mt-1 text-[10px] font-medium opacity-60">
                  {value === 1 ? "order" : "orders"}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      <TableToolbar
        search={list.searchInput}
        onSearchChange={list.setSearch}
        searchPlaceholder="Order number, customer, phone…"
        onRefresh={() => { list.reload(); loadCounts(); }}
        refreshing={list.loading || countsLoading}
        onExport={() => downloadCsv("orders.csv", list.rows, ["order_number", "customer_name", "status", "payment_method", "payment_status", "grand_total", "created_at"])}
        filters={
          <>
            <Select
              aria-label="Filter by status"
              value={list.filters.status || ""}
              onChange={(e) => { list.setFilter("status", e.target.value); setParams(e.target.value ? { status: e.target.value } : {}, { replace: true }); }}
              options={STATUS_FILTERS}
              containerClassName="w-40"
              className="h-9"
            />
            <Select
              aria-label="Filter by payment method"
              value={list.filters.payment_method || ""}
              onChange={(e) => list.setFilter("payment_method", e.target.value)}
              options={PAYMENT_METHODS}
              containerClassName="w-40"
              className="h-9"
            />
          </>
        }
      />

      {list.error ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={list.rows}
            loading={list.loading}
            sort={list.sort}
            onSortChange={list.setSort}
            emptyTitle="No orders match"
            emptyDescription="Orders placed in the storefront will appear here."
            caption="Orders"
          />
          <Pagination
            count={list.count}
            page={list.page}
            pageSize={list.pageSize}
            hasNext={list.hasNext}
            hasPrevious={list.hasPrevious}
            onPageChange={list.setPage}
          />
        </>
      )}
    </div>
  );
}
