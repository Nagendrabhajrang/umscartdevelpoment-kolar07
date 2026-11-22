import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Check, Eye, Pencil, RefreshCw, RotateCcw, X } from "lucide-react";
import Button from "../../components/common/Button";
import Input from "../../components/common/Input";
import Select from "../../components/common/Select";
import Textarea from "../../components/common/Textarea";
import Modal from "../../components/common/Modal";
import Pagination from "../../components/common/Pagination";
import DataTable from "../../components/tables/DataTable";
import TableToolbar from "../../components/tables/TableToolbar";
import { PaymentStatusBadge } from "../../components/common/Badge";
import ErrorState from "../../components/common/ErrorState";
import StatCard from "../../components/charts/StatCard";
import { StatSkeleton } from "../../components/common/Skeleton";
import { useListPage } from "../../hooks/useListPage";
import { useStore } from "../../context/StoreContext";
import { useNotification } from "../../context/NotificationContext";
import { paymentService } from "../../services/paymentService";
import { formatMoney, compactMoney, titleCase, timeAgo } from "../../utils/format";
import { PAYMENT_STATUSES } from "../../utils/constants";

const TABS = [
  { key: "all", label: "All payments" },
  // Every payment is cash on delivery; this queue lists cash not yet handed
  // over. (The old "Awaiting verification" tab was UPI-only.)
  { key: "pending", label: "Cash to collect" },
  { key: "paid", label: "Paid" },
  { key: "refunds", label: "Refunds" },
];

/** Which payment_status each tab asks the API for ("" = no filter). */
const TAB_STATUS = { all: "", pending: "pending", paid: "paid", refunds: "refunded" };

/**
 * Payments desk.
 *
 * The UPI verification flow is the important one here: a customer uploads a
 * transaction reference and screenshot, the payment lands in
 * /payments/pending-verification/, and an admin approves or rejects it here.
 * COD is settled with /cod-collected/.
 */
export default function PaymentsPage() {
  const { dataVersion, bumpDataVersion } = useStore();
  const { notify } = useNotification();

  const [tab, setTab] = useState("all");
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const list = useListPage(paymentService.list, { page_size: 20, ordering: "-created_at" });
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  // Set when we arrived from an order (?collect=<payment id>). After the cash
  // is saved we send the admin straight back to that order.
  const [returnToOrder, setReturnToOrder] = useState(null);
  const [pending, setPending] = useState([]);
  const [tabCounts, setTabCounts] = useState({});
  const [pendingLoading, setPendingLoading] = useState(false);

  // "Record cash" dialog: transaction id + mobile number + feedback.
  const [collectTarget, setCollectTarget] = useState(null); // the payment row
  const [txnId, setTxnId] = useState("");
  const [mobileNumber, setMobileNumber] = useState("");
  const [collectError, setCollectError] = useState(null);

  const [review, setReview] = useState(null);
  const [rejectOpen, setRejectOpen] = useState(null);
  const [refundOpen, setRefundOpen] = useState(null);
  const [viewRow, setViewRow] = useState(null);
  const [reason, setReason] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundFeedback, setRefundFeedback] = useState("");
  const [busy, setBusy] = useState(false);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      setStats(await paymentService.stats());
    } catch {
      setStats(null);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const loadPending = useCallback(async () => {
    setPendingLoading(true);
    try {
      // COD payments whose cash has not been recorded yet.
      const page = await paymentService.list({ status: "pending", page_size: 50 });
      setPending(page.results);
    } catch {
      setPending([]);
    } finally {
      setPendingLoading(false);
    }
  }, []);

  /**
   * One count per tab. The dashboard `stats` endpoint reports
   * `pending_verification` (a UPI concept) and stays 0 for cash, so the badge
   * under "Cash to collect" was always blank. Ask the list endpoint instead.
   */
  const loadCounts = useCallback(async () => {
    try {
      const [all, pendingCount, paidCount, refunded] = await Promise.all([
        paymentService.list({ page_size: 1 }),
        paymentService.list({ status: "pending", page_size: 1 }),
        paymentService.list({ status: "paid", page_size: 1 }),
        paymentService.list({ status: "refunded", page_size: 1 }),
      ]);
      setTabCounts({
        all: all.count,
        pending: pendingCount.count,
        paid: paidCount.count,
        refunds: refunded.count,
      });
    } catch {
      setTabCounts({});
    }
  }, []);

  useEffect(() => { loadStats(); loadCounts(); }, [loadStats, loadCounts, dataVersion]);
  useEffect(() => { if (tab === "pending") loadPending(); }, [tab, loadPending, dataVersion]);
  useEffect(() => { list.reload(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [dataVersion]);

  /**
   * Arriving from an order with `?collect=<id>` opens that payment's cash
   * dialog immediately — "Collect cash first" becomes a real shortcut.
   */
  useEffect(() => {
    const target = searchParams.get("collect");
    if (!target) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const payment = await paymentService.get(target);
        if (!cancelled && payment) {
          openCollect(payment);
          // Where to go back to. `from` in the URL wins (it survives a refresh
          // of this page); otherwise fall back to the payment's order id.
          const from = searchParams.get("from") || payment.order;
          if (from) setReturnToOrder(String(from));
        }
      } catch {
        /* row may be gone - fall back to the plain list */
      } finally {
        if (!cancelled) {
          const next = new URLSearchParams(searchParams);
          next.delete("collect");   // keep `from` so a refresh still knows
          setSearchParams(next, { replace: true });
        }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  /**
   * The tab IS a status filter. Without this the "Refunds" tab showed the
   * same rows as "All payments", which is why it looked broken.
   */
  useEffect(() => {
    list.setFilter("status", TAB_STATUS[tab] ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const approve = async (payment) => {
    setBusy(true);
    try {
      await paymentService.approve(payment.id, { remarks: "Verified against UPI reference" });
      notify.success(`Payment ${payment.payment_number} approved`);
      setReview(null);
      loadStats();
      if (tab === "pending") loadPending(); else list.reload();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not approve this payment.");
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (reason.trim().length < 3) {
      notify.error("Give a reason so the customer knows what went wrong.");
      return;
    }
    setBusy(true);
    try {
      await paymentService.reject(rejectOpen.id, reason.trim());
      notify.success(`Payment ${rejectOpen.payment_number} rejected`);
      setRejectOpen(null);
      setReason("");
      loadStats();
      if (tab === "pending") loadPending(); else list.reload();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not reject this payment.");
    } finally {
      setBusy(false);
    }
  };

  /** True once the cash is in — the dialog then edits instead of collecting. */
  const isSettled = (payment) =>
    Boolean(payment?.is_settled) ||
    ["paid", "verified", "collected"].includes(payment?.payment_status || payment?.status);

  /**
   * One dialog, two modes.
   *  - pending  → record the cash and flip the payment to Paid
   *  - settled  → correct the saved mobile number / UPI id only
   */
  const openCollect = (payment) => {
    setCollectError(null);
    setTxnId(payment.transaction_id || "");
    setMobileNumber(payment.mobile_number || "");
    setCollectTarget(payment);
  };

  const closeCollect = () => {
    if (busy) return;
    setCollectTarget(null);
    setTxnId("");
    setMobileNumber("");
    setCollectError(null);
  };

  /**
   * Record the cash. The two references are optional on the server, but the
   * mobile number is what ties the cash to a person, so it is validated here
   * the same way the API validates it.
   */
  const submitCollect = async () => {
    const phone = mobileNumber.trim();
    if (!phone) {
      setCollectError("Enter the payer's mobile number.");
      return;
    }
    // Normalise: strip spaces, dashes and brackets, then an optional +91 or leading 0.
    const digits = phone
      .replace(/[ \s\-()]/g, "")
      .replace(/^\+91/, "")
      .replace(/^0/, "");
    // Indian mobiles start 6-9; accept any 10 digits so a landline-style
    // entry is not rejected outright, but catch obvious typos.
    if (!(digits.length === 10 && /^\d{10}$/.test(digits))) {
      setCollectError("Enter a 10-digit mobile number, optionally prefixed with +91.");
      return;
    }

    const editing = isSettled(collectTarget);
    setBusy(true);
    setCollectError(null);
    try {
      if (editing) {
        await paymentService.updateReference(collectTarget.id, {
          transaction_id: txnId.trim(),
          mobile_number: phone,
        });
        notify.success(`Payment details updated for ${collectTarget.order_number}`);
      } else {
        await paymentService.markCodCollected(collectTarget.id, {
          amount: collectTarget.amount,
          collected_by: "admin",
          remarks: "Cash recorded in admin console",
          transaction_id: txnId.trim(),
          mobile_number: phone,
        });
        notify.success(`Cash recorded for ${collectTarget.order_number} — marked paid`);
      }
      // Came from an order? Always go back once the save succeeds - whether we
      // just collected the cash or edited the references. That is the page the
      // admin started from.
      const backTo = returnToOrder;
      setCollectTarget(null);
      setTxnId("");
      setMobileNumber("");
      loadPending();
      list.reload();
      loadStats();
      bumpDataVersion();
      if (backTo) {
        setReturnToOrder(null);
        navigate(`/orders/${backTo}`);
      }
    } catch (e) {
      setCollectError(e.message || "Could not save this payment.");
    } finally {
      setBusy(false);
    }
  };

  const issueRefund = async () => {
    setBusy(true);
    try {
      await paymentService.refund(refundOpen.id, {
        amount: refundAmount || refundOpen.amount,
        reason: reason || "Refund approved by admin",
        feedback: refundFeedback.trim(),
      });
      notify.success("Refund recorded");
      setRefundOpen(null);
      setRefundAmount("");
      setReason("");
      setRefundFeedback("");
      list.reload();
      loadStats();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not record the refund.");
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    {
      key: "payment_number",
      header: "Payment",
      sortable: true,
      render: (r) => (
        <div className="space-y-0.5">
          <p className="font-semibold text-slate-900">{r.payment_number}</p>
          <Link to={`/orders/${r.order}`} className="block text-[11px] text-brand-700 hover:underline">
            {r.order_number}
          </Link>
        </div>
      ),
    },
    {
      key: "customer_name",
      header: "Customer",
      render: (r) => <span className="text-xs font-medium text-slate-800">{r.customer_name}</span>,
    },
    {
      key: "amount",
      header: "Amount",
      sortable: true,
      align: "right",
      render: (r) => <span className="font-bold text-slate-900">{formatMoney(r.amount)}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <PaymentStatusBadge status={r.status} />,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => {
        const settled = isSettled(row);
        return (
          <div className="flex justify-end gap-1">
            {/* Pending -> edit (record cash). Paid -> refund. */}
            {settled ? (
              <button type="button" disabled={busy}
                onClick={() => {
                  setRefundOpen(row);
                  setRefundAmount(row.amount);
                  setReason("");
                  setRefundFeedback("");
                }}
                title="Refund"
                className="rounded p-1.5 text-amber-600 hover:bg-amber-50 disabled:opacity-40">
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">Refund {row.payment_number}</span>
              </button>
            ) : (
              <button type="button" disabled={busy} onClick={() => openCollect(row)}
                title="Edit — record transaction id and mobile number"
                className="rounded p-1.5 text-sky-600 hover:bg-sky-50 disabled:opacity-40">
                <Pencil className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">Edit {row.payment_number}</span>
              </button>
            )}
            <button type="button" onClick={() => setViewRow(row)} title="View details"
              className="rounded p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800">
              <Eye className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">View {row.payment_number}</span>
            </button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-3">
      <div>
        <h1 className="page-title">Payments</h1>
        <p className="mt-0.5 text-xs text-slate-500">Record cash received on delivery, track what is outstanding, issue refunds.</p>
      </div>

      {statsLoading && !stats ? (
        <StatSkeleton count={4} />
      ) : stats ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total collected" value={compactMoney(stats.total_amount)} sublabel={`${stats.total_payments} payments`} tone="green" />
          <StatCard label="Settled" value={compactMoney(stats.settled_amount)} sublabel={`${stats.settled_count} settled`} tone="brand" />
          <StatCard
            label="Cash to collect"
            value={String(Math.max(0, (stats.total_payments ?? 0) - (stats.settled_count ?? 0)))}
            sublabel="Deliveries not yet settled"
            tone="amber"
          />
          <StatCard
            label="Payment method"
            value="COD"
            sublabel={`${stats.cod_payments} of ${stats.total_payments} · ${stats.rejected} rejected`}
            tone="violet"
          />
        </div>
      ) : null}

      {/* Tabs */}
      <div className="flex gap-1.5 overflow-x-auto pb-1 no-scrollbar" role="tablist" aria-label="Payment views">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${tab === t.key ? "bg-brand-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"}`}
          >
            {t.label}
            {tabCounts[t.key] > 0 && (
              <span className={`ml-1.5 rounded-full px-1.5 text-[10px] ${tab === t.key ? "bg-white/25 text-white" : "bg-slate-200 text-slate-700"}`}>
                {tabCounts[t.key]}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === "pending" ? (
        pendingLoading ? (
          <div className="space-y-2">{[0, 1].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-white" />)}</div>
        ) : !pending.length ? (
          <div className="card p-8 text-center">
            <Check className="mx-auto h-8 w-8 text-emerald-500" aria-hidden="true" />
            <p className="mt-2 text-sm font-bold text-slate-800">Nothing to verify</p>
            <p className="mt-0.5 text-xs text-slate-500">Every delivery has been settled.</p>
          </div>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {pending.map((payment) => (
              <li key={payment.id} className="card overflow-hidden">
                <div className="flex items-start justify-between gap-2 border-b border-slate-100 bg-amber-50 px-3 py-2">
                  <div>
                    <p className="text-sm font-bold text-slate-900">{payment.order_number}</p>
                    <p className="text-[11px] text-slate-600">{payment.customer_name} · {payment.customer_mobile}</p>
                  </div>
                  <p className="text-base font-extrabold text-slate-900">{formatMoney(payment.amount)}</p>
                </div>
                <div className="grid grid-cols-[88px_1fr] gap-3 p-3">
                  {payment.proof_url ? (
                    <a href={payment.proof_url} target="_blank" rel="noreferrer" className="block">
                      <img src={payment.proof_url} alt="Payment proof" className="h-[88px] w-[88px] rounded-lg border border-slate-200 object-cover" />
                    </a>
                  ) : (
                    <div className="grid h-[88px] w-[88px] place-items-center rounded-lg bg-slate-100 text-[10px] text-slate-400">No image</div>
                  )}
                  <div className="min-w-0 text-xs">
                    <p className="text-slate-500">Reference</p>
                    <p className="truncate font-mono font-semibold text-slate-900">{payment.transaction_id || "—"}</p>
                    <p className="mt-1 text-slate-500">Payer</p>
                    <p className="truncate font-medium text-slate-800">{payment.payer_name || "—"} {payment.upi_id ? `· ${payment.upi_id}` : ""}</p>
                    <p className="mt-1 text-[10px] text-slate-400">Uploaded {timeAgo(payment.payment_proof_uploaded_at || payment.updated_at)}</p>
                  </div>
                </div>
                <div className="flex gap-2 border-t border-slate-100 p-2.5">
                  <Button size="xs" variant="success" className="flex-1" loading={busy} onClick={() => openCollect(payment)}
                    leftIcon={<Pencil className="h-3.5 w-3.5" />}>Record cash</Button>
                </div>
              </li>
            ))}
          </ul>
        )
      ) : (
        <>
          <TableToolbar
            search={list.searchInput}
            onSearchChange={list.setSearch}
            searchPlaceholder="Payment or order number…"
            onRefresh={() => { list.reload(); loadStats(); }}
            refreshing={list.loading}
            filters={
              <>
                <Select aria-label="Filter by method" value={list.filters.method || ""} onChange={(e) => list.setFilter("method", e.target.value)}
                  options={[{ value: "", label: "Any method" }, { value: "cod", label: "Cash on delivery" }]}
                  containerClassName="w-36" className="h-9" />
                <Select aria-label="Filter by status" value={list.filters.status || ""} onChange={(e) => list.setFilter("status", e.target.value)}
                  options={[{ value: "", label: "Any status" }, ...PAYMENT_STATUSES]}
                  containerClassName="w-44" className="h-9" />
              </>
            }
          />
          {list.error ? (
            <ErrorState error={list.error} onRetry={list.reload} />
          ) : (
            <>
              <DataTable columns={columns} rows={list.rows} loading={list.loading} sort={list.sort} onSortChange={list.setSort}
                emptyTitle="No payments" emptyDescription="Payments appear here once orders are placed." caption="Payments" />
              <Pagination count={list.count} page={list.page} pageSize={list.pageSize}
                hasNext={list.hasNext} hasPrevious={list.hasPrevious} onPageChange={list.setPage} />
            </>
          )}
        </>
      )}

      {/* Proof review modal */}
      <Modal open={Boolean(review)} onClose={() => setReview(null)} title={`Review ${review?.payment_number || ""}`} size="lg"
        footer={review && (
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setReview(null)} disabled={busy}>Close</Button>
            <Button variant="danger" size="sm" onClick={() => { setRejectOpen(review); setReason(""); setReview(null); }}
              leftIcon={<X className="h-3.5 w-3.5" />}>Reject</Button>
            <Button variant="success" size="sm" loading={busy} onClick={() => approve(review)} leftIcon={<Check className="h-3.5 w-3.5" />}>
              Approve payment
            </Button>
          </div>
        )}>
        {review && (
          <div className="space-y-3">
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              {[
                ["Order", review.order_number],
                ["Customer", `${review.customer_name} · ${review.customer_mobile}`],
                ["Amount", formatMoney(review.amount)],
                ["Method", review.method_display || titleCase(review.method)],
                ["UPI reference", review.upi_transaction_reference || "—"],
                ["Payer name", review.payer_name || "—"],
                ["Payer UPI ID", review.payer_upi_id || "—"],
                ["Attempts", String(review.verification_attempts ?? 0)],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg bg-slate-50 px-3 py-2">
                  <dt className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{k}</dt>
                  <dd className="font-medium text-slate-800">{v}</dd>
                </div>
              ))}
            </dl>
            {review.notes && <p className="rounded-lg bg-sky-50 px-3 py-2 text-xs text-sky-900">Customer note: {review.notes}</p>}
            {review.proof_url ? (
              <a href={review.proof_url} target="_blank" rel="noreferrer" className="block">
                <img src={review.proof_url} alt="Payment proof" className="max-h-96 w-full rounded-lg border border-slate-200 object-contain" />
              </a>
            ) : (
              <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">
                No screenshot was uploaded for this payment.
              </p>
            )}
          </div>
        )}
      </Modal>

      {/* Reject modal */}
      <Modal open={Boolean(rejectOpen)} onClose={() => setRejectOpen(null)} title="Reject payment proof" size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setRejectOpen(null)} disabled={busy}>Cancel</Button>
            <Button variant="danger" size="sm" onClick={reject} loading={busy}>Reject payment</Button>
          </div>
        }>
        <div className="space-y-3">
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
            The customer will see this reason on their order page and can re-submit proof.
          </p>
          <Textarea label="Reason" required rows={3} value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Reference number does not match any received payment" />
        </div>
      </Modal>

      {/* Refund modal */}
      <Modal open={Boolean(refundOpen)} onClose={() => setRefundOpen(null)} title="Record a refund" size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setRefundOpen(null)} disabled={busy}>Cancel</Button>
            <Button variant="warning" size="sm" onClick={issueRefund} loading={busy}>Record refund</Button>
          </div>
        }>
        <div className="space-y-3">
          <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
            <p className="font-semibold">
              {refundOpen?.payment_number} · {formatMoney(refundOpen?.amount)}
            </p>
            <p className="mt-0.5">
              Paid by {refundOpen?.customer_name}
              {refundOpen?.mobile_number ? ` · ${refundOpen.mobile_number}` : ""}
            </p>
          </div>

          <Input
            label="Refund amount (₹)"
            type="number"
            step="0.01"
            value={refundAmount}
            onChange={(e) => setRefundAmount(e.target.value)}
            hint={`Full amount is ${formatMoney(refundOpen?.amount ?? 0)}.`}
          />

          <Textarea
            label="Reason"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why is this being refunded?"
          />

          <Textarea
            label="Feedback"
            rows={2}
            value={refundFeedback}
            onChange={(e) => setRefundFeedback(e.target.value)}
            placeholder="Anything to note for the record"
            hint="Saved with the refund and shown in the Refund column."
          />
        </div>
      </Modal>

      {/* View: every saved field for this payment, read-only. */}
      <Modal
        open={Boolean(viewRow)}
        onClose={() => setViewRow(null)}
        title="Payment details"
        description={viewRow ? `${viewRow.payment_number} · ${viewRow.order_number}` : undefined}
        size="sm"
        footer={
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={() => setViewRow(null)}>Close</Button>
          </div>
        }
      >
        {viewRow ? (
          <div className="space-y-3">
            <div className="rounded-lg bg-slate-50 px-3 py-2">
              <p className="text-sm font-bold text-slate-900">{formatMoney(viewRow.amount)}</p>
              <p className="mt-0.5 text-xs text-slate-600">
                {viewRow.customer_name}
                {viewRow.customer_mobile ? ` · ${viewRow.customer_mobile}` : ""}
              </p>
              <div className="mt-1.5"><PaymentStatusBadge status={viewRow.status} /></div>
            </div>

            <dl className="divide-y divide-slate-100">
              {[
                ["Transaction ID", viewRow.transaction_id],
                ["Mobile number", viewRow.mobile_number],
                ["Feedback", viewRow.feedback],
                ["Received", viewRow.paid_at ? new Date(viewRow.paid_at).toLocaleString("en-IN") : ""],
                ["Method", viewRow.method_display || viewRow.method],
                ["Order", viewRow.order_number],
              ].map(([label, value]) => (
                <div key={label} className="flex items-start justify-between gap-4 py-2">
                  <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    {label}
                  </dt>
                  <dd className="max-w-[60%] break-words text-right text-xs font-medium text-slate-800">
                    {value || <span className="font-normal text-slate-300">blank</span>}
                  </dd>
                </div>
              ))}
            </dl>

            {viewRow.is_refunded && (
              <div className="rounded-lg bg-amber-50 px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-wide text-amber-700">
                  Refunded {formatMoney(viewRow.refund_amount)}
                </p>
                {(viewRow.refund_feedback || viewRow.refund_reason) && (
                  <p className="mt-0.5 text-xs text-amber-900">
                    {viewRow.refund_feedback || viewRow.refund_reason}
                  </p>
                )}
              </div>
            )}
          </div>
        ) : null}
      </Modal>

      {/* Record cash: two references, then the payment flips to Paid. */}
      <Modal
        open={Boolean(collectTarget)}
        onClose={closeCollect}
        title={isSettled(collectTarget) ? "Edit payment details" : "Record cash received"}
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={closeCollect} disabled={busy}>
              Cancel
            </Button>
            <Button variant="success" size="sm" onClick={submitCollect} loading={busy}
              leftIcon={<Check className="h-3.5 w-3.5" />}>
              {isSettled(collectTarget) ? "Save changes" : "Save & mark paid"}
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          {returnToOrder && (
            <Link
              to={`/orders/${returnToOrder}`}
              onClick={() => setReturnToOrder(null)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-700 hover:underline"
            >
              <ArrowLeft className="h-3 w-3" aria-hidden="true" />
              Back to order
            </Link>
          )}
          <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <p className="font-semibold text-slate-800">
              {collectTarget?.order_number} · {formatMoney(collectTarget?.amount ?? 0)}
            </p>
            <p className="mt-0.5">
              {collectTarget?.customer_name}
              {collectTarget?.customer_mobile ? ` · ${collectTarget.customer_mobile}` : ""}
            </p>
          </div>

          <Input
            label="Transaction ID"
            placeholder="TXN-4821"
            value={txnId}
            onChange={(e) => setTxnId(e.target.value)}
            hint="Cash receipt / transaction reference for this order."
          />

          <Input
            label="Mobile number"
            required
            inputMode="tel"
            placeholder="9876500001"
            value={mobileNumber}
            onChange={(e) => {
              setMobileNumber(e.target.value);
              setCollectError(null);
            }}
            hint="The number the cash was collected from. Saved on the payment."
          />



          {collectError ? (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700">
              {collectError}
            </p>
          ) : null}

          <p className="text-[11px] leading-relaxed text-slate-500">
            {isSettled(collectTarget) ? (
              <>This payment is already recorded. Saving updates only the transaction ID and mobile number.</>
            ) : (
              <>
                Saving records the cash against this order and sets the payment to{" "}
                <span className="font-bold text-slate-700">Paid</span>. The order then becomes
                deliverable.
              </>
            )}
          </p>
        </div>
      </Modal>
    </div>
  );
}
