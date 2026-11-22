import { useCallback, useEffect, useState } from "react";
import { BadgePercent, Calendar, Pencil, Plus, Power, Trash2 } from "lucide-react";
import Button from "../../components/common/Button";
import Select from "../../components/common/Select";
import Modal from "../../components/common/Modal";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import Pagination from "../../components/common/Pagination";
import DataTable from "../../components/tables/DataTable";
import TableToolbar from "../../components/tables/TableToolbar";
import Badge from "../../components/common/Badge";
import ErrorState from "../../components/common/ErrorState";
import StatCard from "../../components/charts/StatCard";
import { StatSkeleton } from "../../components/common/Skeleton";
import PromotionForm from "../../components/forms/PromotionForm";
import { useListPage } from "../../hooks/useListPage";
import { useStore } from "../../context/StoreContext";
import { useNotification } from "../../context/NotificationContext";
import { promotionService } from "../../services/promotionService";
import { catalogService } from "../../services/catalogService";
import { formatMoney, formatDate, formatNumber } from "../../utils/format";

/** Coupons and automatic offers. Toggle, create, edit, delete. */
export default function PromotionsPage() {
  const { dataVersion, bumpDataVersion } = useStore();
  const { notify } = useNotification();

  const list = useListPage(promotionService.list, { page_size: 20, ordering: "-created_at" });
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [categories, setCategories] = useState([]);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [busyId, setBusyId] = useState(null);

  const loadSummary = useCallback(() => {
    setSummaryLoading(true);
    promotionService.summary()
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setSummaryLoading(false));
  }, []);

  useEffect(() => { loadSummary(); }, [loadSummary, dataVersion]);
  useEffect(() => { catalogService.getAllCategories().then(setCategories).catch(() => setCategories([])); }, []);
  useEffect(() => { list.reload(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [dataVersion]);

  const toggle = async (row) => {
    setBusyId(row.id);
    try {
      await promotionService.toggle(row.id);
      notify.success(row.is_active ? "Promotion paused" : "Promotion activated");
      list.reload();
      loadSummary();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not toggle the promotion.");
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await promotionService.remove(deleteTarget.id);
      notify.success("Promotion deleted");
      setDeleteTarget(null);
      list.reload();
      loadSummary();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not delete this promotion.");
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    {
      key: "name",
      header: "Promotion",
      sortable: true,
      render: (r) => (
        <div>
          <p className="font-semibold text-slate-900">{r.name}</p>
          {r.code ? (
            <code className="rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-brand-800">{r.code}</code>
          ) : (
            <span className="text-[11px] text-slate-400">Automatic offer</span>
          )}
        </div>
      ),
    },
    {
      key: "discount_label",
      header: "Discount",
      render: (r) => (
        <div>
          <p className="text-xs font-bold text-emerald-700">{r.discount_label || (r.discount_type === "percentage" ? `${Number(r.discount_value)}% off` : formatMoney(r.discount_value))}</p>
          {Number(r.min_order_value) > 0 && (
            <p className="text-[11px] text-slate-500">Min {formatMoney(r.min_order_value)}</p>
          )}
        </div>
      ),
    },
    {
      key: "usage",
      header: "Usage",
      align: "right",
      render: (r) => (
        <div>
          <p className="text-sm font-semibold tabular-nums text-slate-800">{formatNumber(r.used_count)}</p>
          {r.usage_limit_total && <p className="text-[11px] text-slate-500">of {formatNumber(r.usage_limit_total)}</p>}
        </div>
      ),
    },
    {
      key: "window",
      header: "Window",
      render: (r) => (
        <div className="flex items-center gap-1 text-[11px] text-slate-600">
          <Calendar className="h-3 w-3 text-slate-400" aria-hidden="true" />
          {r.start_date || r.end_date ? `${formatDate(r.start_date)} → ${formatDate(r.end_date)}` : "Always on"}
        </div>
      ),
    },
    {
      key: "state",
      header: "State",
      render: (r) => (
        <div className="flex flex-wrap gap-1">
          <Badge tone={r.is_currently_valid ? "green" : r.is_active ? "amber" : "slate"}>
            {r.is_currently_valid ? "Live" : r.is_active ? "Scheduled / paused" : "Inactive"}
          </Badge>
          {r.is_visible && <Badge tone="blue">Visible</Badge>}
          {r.first_order_only && <Badge tone="violet">1st order</Badge>}
        </div>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => (
        <div className="flex justify-end gap-1">
          <button type="button" onClick={() => toggle(row)} disabled={busyId === row.id} title="Toggle active"
            className="rounded p-1.5 text-slate-500 hover:bg-emerald-50 hover:text-emerald-700 disabled:opacity-40">
            <Power className="h-4 w-4" aria-hidden="true" /><span className="sr-only">Toggle {row.name}</span>
          </button>
          <button type="button" onClick={() => { setEditing(row); setFormOpen(true); }} title="Edit"
            className="rounded p-1.5 text-slate-500 hover:bg-brand-50 hover:text-brand-700">
            <Pencil className="h-4 w-4" aria-hidden="true" /><span className="sr-only">Edit {row.name}</span>
          </button>
          <button type="button" onClick={() => setDeleteTarget(row)} title="Delete"
            className="rounded p-1.5 text-slate-500 hover:bg-rose-50 hover:text-rose-700">
            <Trash2 className="h-4 w-4" aria-hidden="true" /><span className="sr-only">Delete {row.name}</span>
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Promotions</h1>
          <p className="mt-0.5 text-xs text-slate-500">Coupon codes and automatic offers.</p>
        </div>
        <Button onClick={() => { setEditing(null); setFormOpen(true); }} leftIcon={<Plus className="h-4 w-4" />}>New promotion</Button>
      </div>

      {summaryLoading && !summary ? (
        <StatSkeleton count={4} />
      ) : summary ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total promotions" value={formatNumber(summary.total)} icon={BadgePercent} tone="brand" />
          <StatCard label="Active" value={formatNumber(summary.active)} tone="green" />
          <StatCard label="Coupon codes" value={formatNumber(summary.coupons)} tone="sky" />
          <StatCard label="Redemptions" value={formatNumber(summary.total_redemptions)} tone="violet" sublabel={`${summary.expired} expired`} />
        </div>
      ) : null}

      <TableToolbar
        search={list.searchInput}
        onSearchChange={list.setSearch}
        searchPlaceholder="Promotion name or code…"
        onRefresh={() => { list.reload(); loadSummary(); }}
        refreshing={list.loading}
        filters={
          <>
            <Select aria-label="Filter by active state" value={list.filters.is_active || ""} onChange={(e) => list.setFilter("is_active", e.target.value)}
              options={[{ value: "", label: "Any state" }, { value: "true", label: "Active" }, { value: "false", label: "Inactive" }]}
              containerClassName="w-36" className="h-9" />
            <Select aria-label="Filter by discount type" value={list.filters.discount_type || ""} onChange={(e) => list.setFilter("discount_type", e.target.value)}
              options={[{ value: "", label: "Any type" }, { value: "percentage", label: "Percentage" }, { value: "flat", label: "Flat" }]}
              containerClassName="w-36" className="h-9" />
          </>
        }
      />

      {list.error ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : (
        <>
          <DataTable columns={columns} rows={list.rows} loading={list.loading} sort={list.sort} onSortChange={list.setSort}
            emptyTitle="No promotions" emptyDescription="Create a coupon to drive repeat orders."
            emptyAction={<Button size="sm" onClick={() => { setEditing(null); setFormOpen(true); }} leftIcon={<Plus className="h-4 w-4" />}>New promotion</Button>}
            caption="Promotions" />
          <Pagination count={list.count} page={list.page} pageSize={list.pageSize}
            hasNext={list.hasNext} hasPrevious={list.hasPrevious} onPageChange={list.setPage} />
        </>
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? `Edit ${editing.name}` : "New promotion"} size="xl">
        <PromotionForm
          promotion={editing}
          categories={categories}
          onSaved={() => { setFormOpen(false); list.reload(); loadSummary(); bumpDataVersion(); }}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
        loading={deleting}
        title="Delete promotion?"
        description={`"${deleteTarget?.name}" and its redemption history will be removed. Consider pausing it instead if orders reference it.`}
        confirmLabel="Delete promotion"
      />
    </div>
  );
}
