import { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useFetch } from "../../hooks";
import { orderService } from "../../services/orderService";
import { useNotification } from "../../context/NotificationContext";
import { useCart } from "../../context/CartContext";
import { OrderStatusBadge, PaymentStatusBadge } from "../../components/common/Badge";
import Button from "../../components/common/Button";
import Select from "../../components/common/Select";
import Modal from "../../components/common/Modal";
import Skeleton from "../../components/common/Skeleton";
import ErrorState from "../../components/common/ErrorState";
import { formatMoney, formatDateTime, titleCase } from "../../utils/format";
import { CANCELLATION_REASONS } from "../../utils/constants";

/** One order: status timeline, items, bill and the cancellation action. */
export default function OrderDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { notify } = useNotification();
  const { refresh: refreshCart } = useCart();

  /*
   * Round 25: the storefront has no logged-in customer, so /orders/{id}/ is not
   * a safe way to read an order. A fresh checkout or a successful lookup hands
   * the order over in router state; that is the primary source. Without it we
   * show the lookup form rather than asking the API for somebody's order.
   */
  const location = useLocation();
  const passed = location.state?.order ?? null;
  const hasAccess = Boolean(passed);

  const { data: fetched, loading, error, reload } = useFetch(
    () => (hasAccess ? Promise.resolve(passed) : Promise.resolve(null)),
    [id, hasAccess],
  );
  const order = fetched ?? passed;
  const history = { data: order?.status_history ?? [], reload: () => {} };

  const [cancelOpen, setCancelOpen] = useState(false);
  const [reason, setReason] = useState("customer_request");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  if (loading) {
    return (
      <div className="container-page py-6">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="mt-4 h-40 w-full rounded-2xl" />
        <Skeleton className="mt-3 h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-page py-8">
        <ErrorState error={error} onRetry={reload} title="That order could not be loaded" />
      </div>
    );
  }

  if (!order) {
    // No order in hand: send them to the lookup form, which proves ownership
    // with the order number plus the mobile number it was placed with.
    return (
      <div className="container-page py-8">
        <div className="mx-auto max-w-lg rounded-2xl border border-slate-200 bg-white p-6 text-center">
          <h1 className="text-lg font-extrabold text-slate-900">Find your order</h1>
          <p className="mt-1 text-sm text-slate-600">
            Enter your order number and mobile number to see this order.
          </p>
          <Button as={Link} to="/orders" size="lg" className="mt-4">
            Track an order
          </Button>
        </div>
      </div>
    );
  }

  const doCancel = async () => {
    setBusy(true);
    try {
      await orderService.cancel(order.id, reason, note || undefined);
      notify.success("Order cancelled");
      setCancelOpen(false);
      reload();
      history.reload();
    } catch (e) {
      notify.error(e?.message || "Could not cancel that order");
    } finally {
      setBusy(false);
    }
  };

  const doReorder = async () => {
    setBusy(true);
    try {
      await orderService.reorder(order.id);
      await refreshCart();
      notify.success("Items added back to your cart");
      navigate("/cart");
    } catch (e) {
      notify.error(e?.message || "Could not reorder");
    } finally {
      setBusy(false);
    }
  };

  const steps = ["pending", "packed", "out_for_delivery", "delivered", ...(order.status === "returned" || order.status === "refunded" ? ["returned"] : []), ...(order.status === "refunded" ? ["refunded"] : [])];
  const currentStep = steps.indexOf(order.status);
  const cancelled = order.status === "cancelled";

  return (
    <div className="container-page py-6">
      <nav className="mb-3 flex items-center gap-1.5 text-xs text-slate-500" aria-label="Breadcrumb">
        <Link to="/orders" className="hover:text-brand-700">My orders</Link>
        <span aria-hidden="true">/</span>
        <span className="text-slate-700">{order.order_number}</span>
      </nav>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">{order.order_number}</h1>
          <p className="mt-1 text-sm text-slate-600">Placed {formatDateTime(order.created_at)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <OrderStatusBadge status={order.status} />
          <PaymentStatusBadge status={order.payment_status} />
        </div>
      </div>

      {/* Progress */}
      {!cancelled ? (
        <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
          <ol className="flex items-start justify-between gap-1">
            {steps.map((s, i) => {
              const done = i <= currentStep;
              return (
                <li key={s} className="flex flex-1 flex-col items-center text-center">
                  <span
                    className={`grid h-7 w-7 place-items-center rounded-full text-[11px] font-bold ${
                      done ? "bg-brand-600 text-white" : "bg-slate-200 text-slate-500"
                    }`}
                  >
                    {done ? "✓" : i + 1}
                  </span>
                  <span className={`mt-1.5 text-[10px] font-semibold leading-tight ${done ? "text-slate-800" : "text-slate-400"}`}>
                    {titleCase(s)}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      ) : (
        <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3">
          <p className="text-sm font-bold text-rose-900">This order was cancelled</p>
          {order.cancellation_reason ? (
            <p className="mt-0.5 text-xs text-rose-800">
              Reason: {titleCase(order.cancellation_reason)}
            </p>
          ) : null}
        </div>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          {/* Items */}
          <section className="rounded-2xl border border-slate-200 bg-white">
            <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-bold text-slate-900">
              Items ({order.items?.length ?? 0})
            </h2>
            <ul className="divide-y divide-slate-100">
              {(order.items ?? []).map((item) => (
                <li key={item.id} className="flex items-center gap-3 px-4 py-3">
                  <div className="h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-slate-50">
                    {item.product_image_url ? (
                      <img
                        src={item.product_image_url}
                        alt={item.product_name}
                        loading="lazy"
                        className="h-full w-full object-contain"
                      />
                    ) : null}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-slate-900">{item.product_name}</p>
                    <p className="text-[11px] text-slate-500">
                      {item.unit_label} × {item.quantity}
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-bold text-slate-900">{formatMoney(item.line_total)}</p>
                </li>
              ))}
            </ul>
          </section>

          {/* Address — the API flattens it onto the order */}
          {order.full_delivery_address || order.delivery_address_line1 ? (
            <section className="rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-bold text-slate-900">Delivery address</h2>
              <p className="mt-1.5 text-sm font-semibold text-slate-900">
                {order.delivery_recipient_name}
                {order.delivery_recipient_mobile ? (
                  <span className="ml-1.5 font-normal text-slate-500">{order.delivery_recipient_mobile}</span>
                ) : null}
              </p>
              <p className="mt-0.5 text-sm leading-relaxed text-slate-600">
                {order.full_delivery_address ||
                  [
                    order.delivery_address_line1,
                    order.delivery_address_line2,
                    order.delivery_landmark,
                    order.delivery_city,
                    order.delivery_state,
                    order.delivery_pincode,
                  ]
                    .filter(Boolean)
                    .join(", ")}
              </p>
              {order.delivery_instructions ? (
                <p className="mt-1 text-[11px] italic text-slate-500">“{order.delivery_instructions}”</p>
              ) : null}
            </section>
          ) : null}

          {/* History */}
          {history.data?.length ? (
            <section className="rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-bold text-slate-900">Timeline</h2>
              <ol className="mt-2.5 space-y-2.5">
                {history.data.map((h) => (
                  <li key={h.id} className="flex gap-2.5">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                    <div>
                      <p className="text-xs font-semibold text-slate-800">
                        {h.note || titleCase(h.to_status || h.status || "Updated")}
                      </p>
                      <p className="text-[11px] text-slate-500">{formatDateTime(h.created_at)}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}
        </div>

        {/* Bill + actions */}
        <aside className="space-y-3 lg:sticky lg:top-20 lg:self-start">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-bold text-slate-900">Bill</h2>
            <dl className="mt-2.5 space-y-1.5 text-sm">
              <Row label="Item subtotal" value={formatMoney(order.subtotal)} />
              {Number(order.discount_amount) > 0 ? (
                <Row label="Discount" value={`− ${formatMoney(order.discount_amount)}`} positive />
              ) : null}
              <Row label="Delivery" value={Number(order.delivery_charge) > 0 ? formatMoney(order.delivery_charge) : "FREE"} />
              {Number(order.packaging_charge) > 0 ? (
                <Row label="Packaging" value={formatMoney(order.packaging_charge)} />
              ) : null}
              {Number(order.tax_amount) > 0 ? (
                <Row
                  label={order.items?.[0]?.tax_percent ? `Taxes (${order.items[0].tax_percent}%)` : "Taxes"}
                  value={formatMoney(order.tax_amount)}
                />
              ) : null}
              <div className="h-px bg-slate-200" />
              <Row label="Total" value={formatMoney(order.grand_total)} bold />
            </dl>

            <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2">
              <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">Payment</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-800">
                {order.payment_method_display || "Cash on delivery"}
              </p>
            </div>
          </div>

          <div className="space-y-2">
            {order.can_be_cancelled ? (
              <Button variant="secondary" fullWidth onClick={() => setCancelOpen(true)}>
                Cancel order
              </Button>
            ) : null}
            <Button variant="primary" fullWidth onClick={doReorder} loading={busy}>
              Reorder these items
            </Button>
            <Button as={Link} to="/orders" variant="ghost" fullWidth>
              Back to my orders
            </Button>
          </div>
        </aside>
      </div>

      <Modal
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        title="Cancel this order?"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCancelOpen(false)} disabled={busy}>
              Keep order
            </Button>
            <Button variant="danger" onClick={doCancel} loading={busy}>
              Cancel order
            </Button>
          </>
        }
      >
        <Select
          label="Why are you cancelling?"
          options={CANCELLATION_REASONS}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <textarea
          className="mt-3 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          rows={2}
          maxLength={255}
          placeholder="Anything else we should know? (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </Modal>
    </div>
  );
}

function Row({ label, value, positive, bold }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className={`${bold ? "font-bold text-slate-900" : "text-slate-600"}`}>{label}</dt>
      <dd className={`shrink-0 tabular-nums ${positive ? "font-semibold text-brand-700" : bold ? "font-extrabold text-slate-900" : "text-slate-800"}`}>
        {value}
      </dd>
    </div>
  );
}
