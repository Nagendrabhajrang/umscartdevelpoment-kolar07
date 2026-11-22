import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, MapPin, Package, RefreshCw, Truck, Wallet, XCircle } from "lucide-react";
import Button from "../../components/common/Button";
import Input from "../../components/common/Input";
import Modal from "../../components/common/Modal";
import ErrorState from "../../components/common/ErrorState";
import Skeleton from "../../components/common/Skeleton";
import { OrderStatusBadge, PaymentStatusBadge } from "../../components/common/Badge";
import { useStore } from "../../context/StoreContext";
import { useNotification } from "../../context/NotificationContext";
import { orderService } from "../../services/orderService";
import { formatMoney, formatDateTime, titleCase } from "../../utils/format";
import { ORDER_STATUS_LABELS } from "../../utils/constants";

/**
 * Single order fulfilment view.
 *
 * The legal next statuses come from the API (`next_statuses`); the status
 * dropdown is built from that list, so the UI can never request an illegal
 * transition and get a 409.
 */
export default function OrderDetailsPage() {
  const { id } = useParams();
  const { bumpDataVersion } = useStore();
  const { notify } = useNotification();

  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusModal, setStatusModal] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setOrder(await orderService.get(id));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const applyStatus = async () => {
    if (!selectedStatus) return;
    setSaving(true);
    try {
      await orderService.updateStatus(id, selectedStatus, note || undefined);
      notify.success(`Status changed to ${ORDER_STATUS_LABELS[selectedStatus] || selectedStatus}`);
      setStatusModal(false);
      setNote("");
      setSelectedStatus("");
      await load();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "The store rejected that status change.");
    } finally {
      setSaving(false);
    }
  };

  const quickAction = async (action) => {
    setSaving(true);
    try {
      if (action === "confirm") {
        await orderService.confirm(id);
        notify.success("Order confirmed");
      } else {
        await orderService.markDelivered(id);
        notify.success("Order marked delivered");
      }
      await load();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "That action is not allowed right now.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-40" />
        <div className="grid gap-3 lg:grid-cols-3">
          <Skeleton className="h-64 lg:col-span-2" rounded="rounded-xl" />
          <Skeleton className="h-64" rounded="rounded-xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return <ErrorState error={error} onRetry={load} title="Could not load this order" />;
  }
  if (!order) return null;

  // Transitions offered to the admin. "delivered" is stripped out until the
  // cash is in, so the dropdown cannot bypass the same rule the button obeys.
  const rawNext = order.next_statuses || [];
  const isPaidNow = ["paid", "cod_collected"].includes(order.payment_status);
  const next = rawNext.filter((st) => st !== "delivered" || isPaidNow);
  const isFinal = ["delivered", "cancelled", "returned", "refunded"].includes(order.status);

  // Business rule: a product can only be marked delivered once it is paid for.
  // For cash on delivery that means the cash has been recorded; a UPI order
  // would need payment_status=paid. The button stays visible but disabled so
  // the reason is visible instead of the action silently vanishing.
  const isPaid = isPaidNow;

  // The delivery window. While an order sits at "out for delivery" the ONLY
  // thing that matters is the cash: no "Change status" escape hatch, just a
  // link to this order's payment. Once the cash is in, that flips to a single
  // "Mark delivered" button.
  const isOutForDelivery = order.status === "out_for_delivery";
  const awaitingCash = isOutForDelivery && !isPaid;
  // "Change status" is withheld at the delivery window so the flow cannot be
  // side-stepped; everywhere else it stays as before.
  const showChangeStatus = !isFinal && !isOutForDelivery;

  // `from` makes the return trip survive a refresh of the payments page.
  const paymentLink = order.payment_id
    ? `/payments?collect=${order.payment_id}&from=${order.id}`
    : `/payments?from=${order.id}`;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Link to="/orders" className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-200" aria-label="Back to orders">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          </Link>
          <div>
            <h1 className="page-title">{order.order_number}</h1>
            <p className="text-xs text-slate-500">Placed {formatDateTime(order.created_at)}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <Button variant="outline" size="sm" onClick={load} leftIcon={<RefreshCw className="h-3.5 w-3.5" />}>Refresh</Button>
          {next.includes("confirmed") && (
            <Button variant="success" size="sm" loading={saving} onClick={() => quickAction("confirm")} leftIcon={<CheckCircle2 className="h-3.5 w-3.5" />}>
              Confirm order
            </Button>
          )}
          {/* Cash outstanding -> the one action is a link into Payments. */}
          {awaitingCash && (
            <Link
              to={paymentLink}
              className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-amber-500 px-3 text-xs font-semibold text-white shadow-sm transition hover:bg-amber-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-600"
              title="Open this order's payment and record the cash"
            >
              <Wallet className="h-3.5 w-3.5" aria-hidden="true" />
              Collect cash
            </Link>
          )}
          {/* Cash in -> delivery is the one action. */}
          {isOutForDelivery && isPaid && (
            <Button
              variant="primary"
              size="sm"
              loading={saving}
              title="Confirm the delivery"
              onClick={() => quickAction("deliver")}
              leftIcon={<Truck className="h-3.5 w-3.5" />}
            >
              Mark delivered
            </Button>
          )}
          {showChangeStatus && (
            <Button variant="outline" size="sm" onClick={() => setStatusModal(true)}>Change status</Button>
          )}
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          {/* Status banner */}
          <section className="card p-4">
            <div className="flex flex-wrap items-center gap-2">
              <OrderStatusBadge status={order.status} />
              <PaymentStatusBadge status={order.payment_status} />
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold uppercase text-slate-600">
                {order.payment_method_display || titleCase(order.payment_method)}
              </span>
              {order.is_paid && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800">Paid</span>}
            </div>
            {next.length > 0 && (
              <p className="mt-2 text-xs text-slate-500">
                Allowed next steps: {next.map((s) => ORDER_STATUS_LABELS[s] || titleCase(s)).join(" · ")}
              </p>
            )}
            {order.customer_notes && (
              <p className="mt-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs text-amber-900">
                Customer note: {order.customer_notes}
              </p>
            )}
          </section>

          {/* Items */}
          <section className="card p-4">
            <h2 className="mb-2 flex items-center gap-1.5 text-sm font-bold text-slate-900">
              <Package className="h-4 w-4 text-slate-400" aria-hidden="true" /> Items ({order.item_count})
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-[11px] uppercase tracking-wide text-slate-500">
                    <th className="py-2">Product</th>
                    <th className="py-2 text-right">Price</th>
                    <th className="py-2 text-right">Qty</th>
                    <th className="py-2 text-right">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {order.items.map((item) => (
                    <tr key={item.id}>
                      <td className="py-2">
                        <p className="font-medium text-slate-800">{item.product_name}</p>
                        <p className="text-[11px] text-slate-500">{item.product_sku} · {item.unit_label}</p>
                      </td>
                      <td className="py-2 text-right tabular-nums text-slate-600">{formatMoney(item.unit_price)}</td>
                      <td className="py-2 text-right font-semibold tabular-nums text-slate-800">{item.quantity}</td>
                      <td className="py-2 text-right font-bold tabular-nums text-slate-900">{formatMoney(item.line_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* History */}
          <section className="card p-4">
            <h2 className="mb-2 text-sm font-bold text-slate-900">Status history</h2>
            {!order.status_history?.length ? (
              <p className="text-xs text-slate-500">No transitions recorded yet.</p>
            ) : (
              <ol className="relative space-y-2.5 border-l border-slate-200 pl-4">
                {order.status_history.map((h) => (
                  <li key={h.id} className="relative">
                    <span className="absolute -left-[1.15rem] top-1.5 h-2 w-2 rounded-full bg-brand-500 ring-4 ring-white" aria-hidden="true" />
                    <p className="text-xs font-semibold text-slate-900">
                      {h.from_status_display ? `${h.from_status_display} → ` : ""}{h.to_status_display || titleCase(h.to_status)}
                    </p>
                    <p className="text-[11px] text-slate-500">{formatDateTime(h.created_at)}{h.changed_by ? ` · ${h.changed_by}` : ""}</p>
                    {h.note && <p className="text-[11px] text-slate-600">{h.note}</p>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>

        {/* Sidebar: money + delivery */}
        <div className="space-y-3">
          <section className="card p-4">
            <h2 className="mb-2 text-sm font-bold text-slate-900">Bill</h2>
            <dl className="space-y-1.5 text-sm">
              {[
                ["MRP total", formatMoney(order.mrp_total)],
                ["Subtotal", formatMoney(order.subtotal)],
                Number(order.discount_amount) > 0 ? [`Discount${order.coupon_code ? ` (${order.coupon_code})` : ""}`, `− ${formatMoney(order.discount_amount)}`] : null,
                ["Delivery", Number(order.delivery_charge) > 0 ? formatMoney(order.delivery_charge) : "Free"],
                Number(order.packaging_charge) > 0 ? ["Packaging", formatMoney(order.packaging_charge)] : null,
                Number(order.tax_amount) > 0 ? ["GST", formatMoney(order.tax_amount)] : null,
              ].filter(Boolean).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3 text-slate-600">
                  <dt>{k}</dt><dd className="tabular-nums">{v}</dd>
                </div>
              ))}
              <div className="flex justify-between gap-3 border-t border-dashed border-slate-200 pt-2 text-base font-extrabold text-slate-900">
                <dt>Total</dt><dd className="tabular-nums">{formatMoney(order.grand_total)}</dd>
              </div>
            </dl>
            {Number(order.total_savings) > 0 && (
              <p className="mt-2 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-700">
                Customer saved {formatMoney(order.total_savings)}
              </p>
            )}
          </section>

          <section className="card p-4">
            <h2 className="mb-2 flex items-center gap-1.5 text-sm font-bold text-slate-900">
              <MapPin className="h-4 w-4 text-slate-400" aria-hidden="true" /> Delivery
            </h2>
            <p className="text-sm font-semibold text-slate-900">{order.delivery_recipient_name}</p>
            <p className="text-xs text-slate-500">{order.delivery_recipient_mobile}</p>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{order.full_delivery_address}</p>
            {order.delivery_instructions && (
              <p className="mt-1.5 rounded bg-amber-50 px-2 py-1 text-[11px] text-amber-800">{order.delivery_instructions}</p>
            )}
          </section>

          <section className="card p-4">
            <h2 className="mb-2 text-sm font-bold text-slate-900">Customer</h2>
            <p className="text-sm font-semibold text-slate-900">{order.customer_name}</p>
            <p className="text-xs text-slate-500">{order.customer_mobile}</p>
            <Link to={`/customers/${order.customer}`} className="mt-2 inline-block text-xs font-semibold text-brand-700 hover:underline">
              View customer profile →
            </Link>
          </section>
        </div>
      </div>

      <Modal
        open={statusModal}
        onClose={() => setStatusModal(false)}
        title="Change order status"
        description="Only transitions the store allows are listed."
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setStatusModal(false)} disabled={saving}>Cancel</Button>
            <Button size="sm" onClick={applyStatus} loading={saving} disabled={!selectedStatus}>Apply</Button>
          </div>
        }
      >
        <div className="space-y-3">
          <div>
            <label htmlFor="next-status" className="mb-1 block text-xs font-semibold text-slate-600">Next status</label>
            <select
              id="next-status"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="h-10 w-full rounded-lg border border-slate-300 px-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
            >
              <option value="">Choose…</option>
              {next.map((s) => <option key={s} value={s}>{ORDER_STATUS_LABELS[s] || titleCase(s)}</option>)}
            </select>
          </div>
          <Input label="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Packed by Ravi" />
          {!next.length && <p className="text-xs text-slate-500">This order has no further transitions available.</p>}
        </div>
      </Modal>
    </div>
  );
}
