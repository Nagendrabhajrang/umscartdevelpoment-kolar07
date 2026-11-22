import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowDownCircle, ArrowUpCircle, History, Package, Save } from "lucide-react";
import Button from "../../components/common/Button";
import Input from "../../components/common/Input";
import Select from "../../components/common/Select";
import Modal from "../../components/common/Modal";
import Pagination from "../../components/common/Pagination";
import DataTable from "../../components/tables/DataTable";
import TableToolbar from "../../components/tables/TableToolbar";
import ErrorState from "../../components/common/ErrorState";
import StatCard from "../../components/charts/StatCard";
import { StatSkeleton } from "../../components/common/Skeleton";
import Badge from "../../components/common/Badge";
import StockAdjustForm from "../../components/forms/StockAdjustForm";
import { useListPage } from "../../hooks/useListPage";
import { useStore } from "../../context/StoreContext";
import { useNotification } from "../../context/NotificationContext";
import { inventoryService } from "../../services/inventoryService";
import { formatNumber, formatDateTime, titleCase, timeAgo } from "../../utils/format";

/**
 * Inventory: live stock levels plus the movement audit trail.
 *
 * Every quantity change goes through /inventory/stock/{id}/add|remove/, which
 * records a movement row - so the "Movements" tab always explains why stock
 * is what it is.
 */
export default function InventoryPage() {
  const { dataVersion, bumpDataVersion } = useStore();
  const { notify } = useNotification();

  const [tab, setTab] = useState("stock");
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  const list = useListPage(inventoryService.listStock, { page_size: 20, ordering: "quantity" });
  const movements = useListPage(inventoryService.listMovements, { page_size: 20, ordering: "-created_at" });

  const [adjustTarget, setAdjustTarget] = useState(null);
  const [adjustMode, setAdjustMode] = useState("add");
  const [thresholdTarget, setThresholdTarget] = useState(null);
  const [thresholdValue, setThresholdValue] = useState("");
  const [busy, setBusy] = useState(false);

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    try {
      setSummary(await inventoryService.summary());
    } catch {
      setSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  useEffect(() => { loadSummary(); }, [loadSummary, dataVersion]);
  useEffect(() => { list.reload(); movements.reload(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [dataVersion]);

  const saveThreshold = async () => {
    setBusy(true);
    try {
      await inventoryService.setThreshold(thresholdTarget.id, Number(thresholdValue));
      notify.success("Low-stock threshold updated");
      setThresholdTarget(null);
      list.reload();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not update the threshold.");
    } finally {
      setBusy(false);
    }
  };

  const toggleTracking = async (row) => {
    try {
      await inventoryService.setTracking(row.id, !row.track_inventory);
      notify.success(row.track_inventory ? "Tracking disabled" : "Tracking enabled");
      list.reload();
    } catch (e) {
      notify.error(e.message || "Could not change tracking.");
    }
  };

  const stockColumns = [
    {
      key: "product_name",
      header: "Product",
      sortable: true,
      render: (r) => (
        <div>
          <p className="font-semibold text-slate-900">{r.product_name}</p>
          <p className="text-[11px] text-slate-500">{r.product_sku}</p>
        </div>
      ),
    },
    {
      key: "quantity",
      header: "On hand",
      sortable: true,
      align: "right",
      render: (r) => <span className="font-bold tabular-nums text-slate-900">{formatNumber(r.quantity)}</span>,
    },
    {
      key: "reserved_quantity",
      header: "Reserved",
      align: "right",
      render: (r) => <span className="text-xs tabular-nums text-slate-500">{formatNumber(r.reserved_quantity)}</span>,
    },
    {
      key: "quantity_available",
      header: "Available",
      sortable: true,
      align: "right",
      render: (r) => {
        const q = r.quantity_available ?? 0;
        return <span className={`font-semibold tabular-nums ${q <= 0 ? "text-rose-600" : q <= (r.low_stock_threshold || 5) ? "text-amber-600" : "text-emerald-700"}`}>{formatNumber(q)}</span>;
      },
    },
    {
      key: "low_stock_threshold",
      header: "Alert at",
      align: "right",
      render: (r) => (
        <button type="button" onClick={() => { setThresholdTarget(r); setThresholdValue(String(r.low_stock_threshold ?? 5)); }}
          className="rounded px-2 py-0.5 text-xs font-semibold text-brand-700 hover:bg-brand-50">
          {r.low_stock_threshold ?? 5}
        </button>
      ),
    },
    {
      key: "flags",
      header: "Status",
      render: (r) => (
        <div className="flex flex-wrap gap-1">
          {r.is_out_of_stock ? <Badge tone="red">Out of stock</Badge>
            : r.is_low_stock ? <Badge tone="amber">Low</Badge>
            : <Badge tone="green">Healthy</Badge>}
          {!r.track_inventory && <Badge tone="slate">Untracked</Badge>}
        </div>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => (
        <div className="flex justify-end gap-1">
          <button type="button" onClick={() => { setAdjustTarget(row); setAdjustMode("add"); }} title="Add stock"
            className="rounded p-1.5 text-emerald-600 hover:bg-emerald-50">
            <ArrowUpCircle className="h-4 w-4" aria-hidden="true" /><span className="sr-only">Add stock for {row.product_name}</span>
          </button>
          <button type="button" onClick={() => { setAdjustTarget(row); setAdjustMode("remove"); }} title="Remove stock"
            className="rounded p-1.5 text-rose-600 hover:bg-rose-50">
            <ArrowDownCircle className="h-4 w-4" aria-hidden="true" /><span className="sr-only">Remove stock for {row.product_name}</span>
          </button>
          <button type="button" onClick={() => toggleTracking(row)} title="Toggle tracking"
            className="rounded p-1.5 text-slate-500 hover:bg-slate-100">
            <Package className="h-4 w-4" aria-hidden="true" /><span className="sr-only">Toggle tracking for {row.product_name}</span>
          </button>
        </div>
      ),
    },
  ];

  const movementColumns = [
    {
      key: "created_at",
      header: "When",
      sortable: true,
      render: (r) => (
        <div>
          <p className="text-xs font-medium text-slate-800">{formatDateTime(r.created_at)}</p>
          <p className="text-[10px] text-slate-400">{timeAgo(r.created_at)}</p>
        </div>
      ),
    },
    { key: "product_name", header: "Product", render: (r) => <span className="text-xs font-medium text-slate-800">{r.product_name || r.product}</span> },
    {
      key: "movement_type",
      header: "Type",
      render: (r) => <Badge tone={["purchase", "return", "initial"].includes(r.movement_type) ? "green" : ["damage", "adjustment"].includes(r.movement_type) ? "amber" : "slate"}>{titleCase(r.movement_type)}</Badge>,
    },
    {
      key: "quantity_change",
      header: "Change",
      align: "right",
      render: (r) => {
        const change = r.quantity_change ?? r.quantity ?? 0;
        return <span className={`font-bold tabular-nums ${Number(change) >= 0 ? "text-emerald-700" : "text-rose-600"}`}>{Number(change) > 0 ? "+" : ""}{formatNumber(change)}</span>;
      },
    },
    { key: "reason", header: "Reason", render: (r) => <span className="text-xs text-slate-600">{r.reason || "—"}</span> },
    { key: "reference", header: "Reference", render: (r) => <span className="font-mono text-[11px] text-slate-500">{r.reference || "—"}</span> },
  ];

  const active = tab === "stock" ? list : movements;

  return (
    <div className="space-y-3">
      <div>
        <h1 className="page-title">Inventory</h1>
        <p className="mt-0.5 text-xs text-slate-500">Stock levels, adjustments and a full movement log.</p>
      </div>

      {summaryLoading && !summary ? (
        <StatSkeleton count={4} />
      ) : summary ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Tracked products" value={formatNumber(summary.total_products)} icon={Package} tone="brand" />
          <StatCard label="Total units" value={formatNumber(summary.total_units)} icon={Package} tone="sky" />
          <StatCard label="Low stock" value={formatNumber(summary.low_stock)} icon={AlertTriangle} tone="amber" sublabel="Below alert threshold" />
          <StatCard label="Out of stock" value={formatNumber(summary.out_of_stock)} icon={AlertTriangle} tone="rose" sublabel="Needs restocking now" />
        </div>
      ) : null}

      <div className="flex gap-1.5" role="tablist" aria-label="Inventory views">
        {[
          { key: "stock", label: "Stock levels", icon: Package },
          { key: "movements", label: "Movement log", icon: History },
        ].map(({ key, label, icon: Icon }) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${tab === key ? "bg-brand-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"}`}>
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />{label}
          </button>
        ))}
      </div>

      <TableToolbar
        search={active.searchInput}
        onSearchChange={active.setSearch}
        searchPlaceholder={tab === "stock" ? "Search products…" : "Search movements…"}
        onRefresh={() => { active.reload(); loadSummary(); }}
        refreshing={active.loading}
        filters={tab === "stock" ? (
          <Select aria-label="Filter stock by state" value={list.filters.low_stock || ""} onChange={(e) => list.setFilter("low_stock", e.target.value)}
            options={[{ value: "", label: "All items" }, { value: "true", label: "Low stock only" }]} containerClassName="w-40" className="h-9" />
        ) : (
          <Select aria-label="Filter by movement type" value={movements.filters.movement_type || ""} onChange={(e) => movements.setFilter("movement_type", e.target.value)}
            options={[
              { value: "", label: "All types" },
              { value: "purchase", label: "Purchase" },
              { value: "sale", label: "Sale" },
              { value: "adjustment", label: "Adjustment" },
              { value: "return", label: "Return" },
              { value: "damage", label: "Damage" },
              { value: "initial", label: "Initial" },
              { value: "reservation", label: "Reservation" },
              { value: "release", label: "Release" },
            ]}
            containerClassName="w-40" className="h-9" />
        )}
      />

      {active.error ? (
        <ErrorState error={active.error} onRetry={active.reload} />
      ) : (
        <>
          <DataTable
            columns={tab === "stock" ? stockColumns : movementColumns}
            rows={active.rows}
            loading={active.loading}
            sort={active.sort}
            onSortChange={active.setSort}
            emptyTitle={tab === "stock" ? "No stock records" : "No movements yet"}
            emptyDescription={tab === "stock" ? "Stock rows are created when a product is added to inventory." : "Stock changes will be logged here."}
            caption={tab === "stock" ? "Stock levels" : "Stock movements"}
          />
          <Pagination count={active.count} page={active.page} pageSize={active.pageSize}
            hasNext={active.hasNext} hasPrevious={active.hasPrevious} onPageChange={active.setPage} />
        </>
      )}

      <Modal open={Boolean(adjustTarget)} onClose={() => setAdjustTarget(null)} title="Adjust stock" size="sm">
        {adjustTarget && (
          <StockAdjustForm stock={adjustTarget} mode={adjustMode}
            onSaved={() => { setAdjustTarget(null); list.reload(); movements.reload(); loadSummary(); bumpDataVersion(); }}
            onCancel={() => setAdjustTarget(null)} />
        )}
      </Modal>

      <Modal open={Boolean(thresholdTarget)} onClose={() => setThresholdTarget(null)} title="Low-stock alert threshold" size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setThresholdTarget(null)} disabled={busy}>Cancel</Button>
            <Button size="sm" onClick={saveThreshold} loading={busy} leftIcon={<Save className="h-3.5 w-3.5" />}>Save</Button>
          </div>
        }>
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            Alert when <span className="font-semibold text-slate-900">{thresholdTarget?.product_name}</span> drops to or below this quantity.
          </p>
          <Input label="Threshold" type="number" min="0" value={thresholdValue} onChange={(e) => setThresholdValue(e.target.value)} autoFocus />
        </div>
      </Modal>
    </div>
  );
}
