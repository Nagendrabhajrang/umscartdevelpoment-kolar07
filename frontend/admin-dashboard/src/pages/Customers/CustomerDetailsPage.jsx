import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CalendarDays, CreditCard, Eye, Mail, MapPin, Phone, Plus, ShieldCheck, ShoppingBag, StickyNote, TrendingUp } from "lucide-react";
import Button from "../../components/common/Button";
import Textarea from "../../components/common/Textarea";
import ErrorState from "../../components/common/ErrorState";
import Skeleton from "../../components/common/Skeleton";
import Badge, { OrderStatusBadge, PaymentStatusBadge } from "../../components/common/Badge";
import StatCard from "../../components/charts/StatCard";
import { useNotification } from "../../context/NotificationContext";
import { customerService } from "../../services/customerService";
import { orderService } from "../../services/orderService";
import { paymentService } from "../../services/paymentService";
import { addressService } from "../../services/addressService";
import { formatMoney, formatDate, formatDateTime, titleCase } from "../../utils/format";

/**
 * 360° view of one customer: profile, spend, order history, addresses and the
 * internal notes log (`POST /customers/{id}/notes/`).
 */
export default function CustomerDetailsPage() {
  const { id } = useParams();
  const { notify } = useNotification();

  const [customer, setCustomer] = useState(null);
  const [orders, setOrders] = useState([]);
  const [addresses, setAddresses] = useState([]);
  const [notes, setNotes] = useState([]);
  const [payments, setPayments] = useState([]);
  // Order id whose product lines are shown inline ("View" toggle).
  const [openOrder, setOpenOrder] = useState(null);
  const [orderDetail, setOrderDetail] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newNote, setNewNote] = useState("");
  const [savingNote, setSavingNote] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const record = await customerService.get(id);
      setCustomer(record);

      const [ordersPage, addressesPage, notesPage, paymentsPage] = await Promise.allSettled([
        orderService.list({ customer: id, page_size: 50, ordering: "-created_at" }),
        addressService.list({ customer: id, page_size: 20 }),
        customerService.notes(id, { page_size: 20 }),
        paymentService.list({ customer: id, page_size: 50, ordering: "-created_at" }),
      ]);

      setOrders(ordersPage.status === "fulfilled" ? ordersPage.value.results : []);
      setAddresses(addressesPage.status === "fulfilled" ? (Array.isArray(addressesPage.value) ? addressesPage.value : addressesPage.value.results) : []);
      setNotes(notesPage.status === "fulfilled" ? notesPage.value.results : []);
      setPayments(paymentsPage.status === "fulfilled" ? paymentsPage.value.results : []);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  /** Fetch and cache one order's line items, for the inline "View" toggle. */
  const toggleOrder = async (order) => {
    if (openOrder === order.id) { setOpenOrder(null); return; }
    setOpenOrder(order.id);
    if (orderDetail[order.id]) return;          // already cached
    try {
      const detail = await orderService.get(order.id);
      setOrderDetail((prev) => ({ ...prev, [order.id]: detail }));
    } catch (e) {
      notify.error(e.message || "Could not load this order's items.");
    }
  };

  const addNote = async () => {
    if (newNote.trim().length < 2) return;
    setSavingNote(true);
    try {
      await customerService.addNote(id, newNote.trim());
      setNewNote("");
      const page = await customerService.notes(id, { page_size: 20 });
      setNotes(page.results);
      notify.success("Note added");
    } catch (e) {
      notify.error(e.message || "Could not add the note.");
    } finally {
      setSavingNote(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-7 w-48" />
        <div className="grid gap-3 sm:grid-cols-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-24" rounded="rounded-xl" />)}
        </div>
        <Skeleton className="h-64" rounded="rounded-xl" />
      </div>
    );
  }

  if (error) return <ErrorState error={error} onRetry={load} title="Could not load this customer" />;
  if (!customer) return null;

  // ---- figures derived from the loaded orders / payments ---------------
  const deliveredOrders = orders.filter((o) => o.status === "delivered");
  const cancelledOrders = orders.filter((o) => o.status === "cancelled");
  const inFlight = orders.filter((o) =>
    ["pending", "confirmed", "processing", "packed", "out_for_delivery"].includes(o.status));
  const unpaidOrders = orders.filter((o) => !o.is_paid && o.status !== "cancelled");
  const refusedOrders = orders.filter((o) => ["returned", "refunded"].includes(o.status));
  const totalPaid = payments
    .filter((p) => ["paid", "collected", "cod_collected"].includes(p.payment_status))
    .reduce((sum, p) => sum + Number(p.amount || 0), 0);
  const totalRefunded = payments
    .filter((p) => p.payment_status === "refunded")
    .reduce((sum, p) => sum + Number(p.amount || 0), 0);
  const pendingCash = payments
    .filter((p) => p.payment_status === "pending")
    .reduce((sum, p) => sum + Number(p.amount || 0), 0);
  const avgOrder = deliveredOrders.length
    ? deliveredOrders.reduce((a, o) => a + Number(o.grand_total || 0), 0) / deliveredOrders.length
    : 0;

  // Every status change across every order, newest first - the full trail.
  const timeline = orders
    .flatMap((o) =>
      (o.status_history || []).map((h) => ({ ...h, order: o })),
    )
    .filter((h) => h.created_at)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 40);

  // Fall back to the order's own timestamps when no history rows exist.
  const fallbackTimeline = orders
    .map((o) => ({ order: o, created_at: o.updated_at }))
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 20);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Link to="/customers" className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-200" aria-label="Back to customers">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        </Link>
        <div className="flex-1">
          <h1 className="page-title">{customer.full_name}</h1>
          <p className="text-xs text-slate-500">Joined {formatDate(customer.created_at)} · ID #{customer.id}</p>
        </div>
        <Badge tone={customer.status === "active" ? "green" : customer.status === "blocked" ? "red" : "slate"}>
          {titleCase(customer.status)}
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Total orders" value={String(customer.order_count)} icon={ShoppingBag} tone="brand" />
        <StatCard label="Delivered" value={String(deliveredOrders.length)} icon={ShieldCheck} tone="green" />
        <StatCard label="In progress" value={String(inFlight.length)} icon={TrendingUp} tone="sky" />
        <StatCard label="Total paid" value={formatMoney(totalPaid || customer.lifetime_value)} icon={CreditCard} tone="green" />
        <StatCard label="Addresses" value={String(customer.address_count)} icon={MapPin} tone="sky" />
      </div>

      {/* Money + behaviour strip */}
      <div className="card grid grid-cols-2 gap-3 p-3 sm:grid-cols-3 lg:grid-cols-6">
        {[
          ["Avg order value", formatMoney(avgOrder), "text-slate-900"],
          ["Cash pending", formatMoney(pendingCash), pendingCash > 0 ? "text-amber-700" : "text-slate-900"],
          ["Refunded", formatMoney(totalRefunded), totalRefunded > 0 ? "text-violet-700" : "text-slate-900"],
          ["Unpaid orders", String(unpaidOrders.length), unpaidOrders.length ? "text-amber-700" : "text-slate-900"],
          ["Cancelled", String(cancelledOrders.length), "text-slate-900"],
          ["Returned / refunded", String(refusedOrders.length), "text-slate-900"],
        ].map(([label, value, cls]) => (
          <div key={label}>
            <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{label}</p>
            <p className={`mt-0.5 text-sm font-extrabold ${cls}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          <section className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900">
                Orders
                <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 text-[10px] font-semibold text-slate-600">
                  {orders.length}
                </span>
              </h2>
              <span className="text-[11px] text-slate-500">Tap View to see what was ordered</span>
            </div>
            {!orders.length ? (
              <p className="rounded-lg bg-slate-50 px-3 py-4 text-center text-xs text-slate-500">This customer has not ordered yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {orders.map((order) => {
                  const open = openOrder === order.id;
                  const detail = orderDetail[order.id];
                  return (
                    <li key={order.id} className="py-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-slate-900">{order.order_number}</p>
                          <p className="text-[11px] text-slate-500">
                            {formatDateTime(order.created_at)}
                            {order.item_count ? ` · ${order.item_count} item${order.item_count === 1 ? "" : "s"}` : ""}
                          </p>
                        </div>
                        <OrderStatusBadge status={order.status} />
                        <span className="w-20 text-right text-xs font-bold tabular-nums text-slate-900">
                          {formatMoney(order.grand_total)}
                        </span>
                        <button
                          type="button"
                          onClick={() => toggleOrder(order)}
                          aria-expanded={open}
                          title={open ? "Hide products" : "View products in this order"}
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50"
                        >
                          <Eye className="h-3 w-3" aria-hidden="true" />
                          {open ? "Hide" : "View"}
                        </button>
                      </div>

                      {open && (
                        <div className="mt-2 rounded-lg bg-slate-50 p-2">
                          {!detail ? (
                            <p className="px-1 py-2 text-[11px] text-slate-500">Loading products…</p>
                          ) : (
                            <>
                              <table className="w-full text-left text-[11px]">
                                <thead>
                                  <tr className="text-[10px] uppercase tracking-wide text-slate-400">
                                    <th className="py-1">Product</th>
                                    <th className="py-1 text-right">Qty</th>
                                    <th className="py-1 text-right">Price</th>
                                    <th className="py-1 text-right">Total</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200">
                                  {(detail.items || []).map((it) => (
                                    <tr key={it.id}>
                                      <td className="py-1.5 pr-2">
                                        <div className="flex items-center gap-2">
                                          {it.product_image_url ? (
                                            <img src={it.product_image_url} alt="" className="h-7 w-7 rounded object-cover" />
                                          ) : (
                                            <span className="grid h-7 w-7 place-items-center rounded bg-slate-200 text-[9px] text-slate-500">—</span>
                                          )}
                                          <div className="min-w-0">
                                            <p className="truncate font-semibold text-slate-800">{it.product_name}</p>
                                            <p className="text-[10px] text-slate-500">{it.product_sku}{it.unit_label ? ` · ${it.unit_label}` : ""}</p>
                                          </div>
                                        </div>
                                      </td>
                                      <td className="py-1.5 text-right tabular-nums text-slate-700">{it.quantity}</td>
                                      <td className="py-1.5 text-right tabular-nums text-slate-700">{formatMoney(it.unit_price)}</td>
                                      <td className="py-1.5 text-right font-semibold tabular-nums text-slate-900">{formatMoney(it.line_total)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                              <div className="mt-1.5 flex flex-wrap items-center justify-between gap-1 border-t border-slate-200 pt-1.5 text-[10px] text-slate-500">
                                <span>
                                  Subtotal {formatMoney(detail.subtotal)} · Delivery {formatMoney(detail.delivery_charge)} · Tax {formatMoney(detail.tax_amount)}
                                </span>
                                <Link to={`/orders/${order.id}`} className="font-semibold text-brand-700 hover:underline">
                                  Open order →
                                </Link>
                              </div>
                            </>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="card p-4">
            <h2 className="mb-2 flex items-center gap-1.5 text-sm font-bold text-slate-900">
              <CalendarDays className="h-4 w-4 text-slate-400" aria-hidden="true" /> Tracking history
              <span className="ml-1 rounded-full bg-slate-100 px-1.5 text-[10px] font-semibold text-slate-600">
                {timeline.length || fallbackTimeline.length}
              </span>
            </h2>
            {!(timeline.length || orders.length) ? (
              <p className="rounded-lg bg-slate-50 px-3 py-4 text-center text-xs text-slate-500">No activity yet.</p>
            ) : (
              <ol className="relative ml-2 border-l border-slate-200 pl-4">
                {(timeline.length ? timeline : fallbackTimeline).map((row, i) => {
                  const o = row.order;
                  const to = row.to_status;
                  const from = row.from_status;
                  return (
                    <li key={`${o.id}-${row.id ?? i}`} className="relative pb-3 last:pb-0">
                      <span className={`absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full ring-2 ring-white ${
                        to === "delivered" ? "bg-emerald-500"
                        : to === "cancelled" ? "bg-rose-500"
                        : to === "returned" || to === "refunded" ? "bg-violet-500"
                        : "bg-sky-500"
                      }`} aria-hidden="true" />
                      <div className="flex flex-wrap items-center gap-1.5">
                        <OrderStatusBadge status={to || o.status} />
                        <Link to={`/orders/${o.id}`} className="text-[11px] font-bold text-brand-700 hover:underline">
                          {o.order_number}
                        </Link>
                        {from && from !== to && (
                          <span className="text-[10px] text-slate-400">{titleCase(from)} → {titleCase(to)}</span>
                        )}
                      </div>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        {formatDateTime(row.created_at)}
                        {row.changed_by ? ` · ${row.changed_by}` : ""}
                        {row.note ? ` · ${row.note}` : ""}
                      </p>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>

          <section className="card p-4">
            <h2 className="mb-2 flex items-center gap-1.5 text-sm font-bold text-slate-900">
              <CreditCard className="h-4 w-4 text-slate-400" aria-hidden="true" /> Payments
              <span className="ml-1 rounded-full bg-slate-100 px-1.5 text-[10px] font-semibold text-slate-600">
                {payments.length}
              </span>
            </h2>
            {!payments.length ? (
              <p className="rounded-lg bg-slate-50 px-3 py-4 text-center text-xs text-slate-500">No payments recorded.</p>
            ) : (
              <div className="relative min-w-0 overflow-x-auto">
                <table className="w-full min-w-[560px] text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-[10px] uppercase tracking-wide text-slate-500">
                      <th className="py-1.5">Payment</th>
                      <th className="py-1.5">Transaction</th>
                      <th className="py-1.5">Mobile</th>
                      <th className="py-1.5 text-right">Amount</th>
                      <th className="py-1.5">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {payments.map((pay) => (
                      <tr key={pay.id}>
                        <td className="py-1.5">
                          <p className="font-semibold text-slate-900">{pay.payment_number}</p>
                          <p className="text-[10px] text-slate-500">{formatDate(pay.created_at)}</p>
                        </td>
                        <td className="py-1.5 font-mono text-[11px] text-slate-700">
                          {pay.transaction_id || <span className="text-slate-300">blank</span>}
                        </td>
                        <td className="py-1.5 text-[11px] text-slate-700">
                          {pay.mobile_number || <span className="text-slate-300">blank</span>}
                        </td>
                        <td className="py-1.5 text-right font-bold tabular-nums text-slate-900">{formatMoney(pay.amount)}</td>
                        <td className="py-1.5"><PaymentStatusBadge status={pay.payment_status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="card p-4">
            <h2 className="mb-2 flex items-center gap-1.5 text-sm font-bold text-slate-900">
              <StickyNote className="h-4 w-4 text-slate-400" aria-hidden="true" /> Internal notes
            </h2>
            <div className="mb-3">
              <Textarea
                aria-label="New internal note"
                rows={2}
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                placeholder="e.g. Prefers evening deliveries. Called about a delayed order."
              />
              <div className="mt-1.5 flex justify-end">
                <Button size="xs" onClick={addNote} loading={savingNote} disabled={newNote.trim().length < 2}
                  leftIcon={<Plus className="h-3 w-3" />}>Add note</Button>
              </div>
            </div>
            {!notes.length ? (
              <p className="text-xs text-slate-500">No notes yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {notes.map((note) => (
                  <li key={note.id} className="rounded-lg bg-amber-50 px-3 py-2">
                    <p className="text-xs text-amber-900">{note.note}</p>
                    <p className="mt-0.5 text-[10px] text-amber-700">{formatDateTime(note.created_at)}{note.created_by ? ` · ${note.created_by}` : ""}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <div className="space-y-3">
          <section className="card p-4">
            <h2 className="mb-2 text-sm font-bold text-slate-900">Contact</h2>
            <ul className="space-y-1.5 text-xs">
              <li className="flex items-center gap-2 text-slate-700">
                <Phone className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" /> {customer.mobile_number}
                {customer.is_mobile_verified && <Badge tone="green">Verified</Badge>}
              </li>
              {customer.email && (
                <li className="flex items-center gap-2 break-all text-slate-700">
                  <Mail className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true" /> {customer.email}
                </li>
              )}
              <li className="text-[11px] text-slate-500">Last login: {customer.last_login_at ? formatDateTime(customer.last_login_at) : "—"}</li>
            </ul>
            {customer.notes && (
              <p className="mt-2 rounded-lg bg-slate-50 px-2.5 py-1.5 text-[11px] text-slate-600">{customer.notes}</p>
            )}
          </section>

          <section className="card p-4">
            <h2 className="mb-2 flex items-center gap-1.5 text-sm font-bold text-slate-900">
              <MapPin className="h-4 w-4 text-slate-400" aria-hidden="true" /> Addresses
            </h2>
            {!addresses.length ? (
              <p className="text-xs text-slate-500">No saved addresses.</p>
            ) : (
              <ul className="space-y-2">
                {addresses.map((addr) => (
                  <li key={addr.id} className="rounded-lg bg-slate-50 px-2.5 py-2 text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-slate-900">{addr.recipient_name}</span>
                      <Badge tone="slate">{titleCase(addr.label)}</Badge>
                      {addr.is_default && <Badge tone="indigo">Default</Badge>}
                    </div>
                    <p className="mt-0.5 leading-relaxed text-slate-600">{addr.full_address}</p>
                    <p className="text-slate-500">{addr.recipient_mobile}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
