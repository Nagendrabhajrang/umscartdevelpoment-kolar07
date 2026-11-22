import { useEffect, useState } from "react";
import { Eye, EyeOff, MousePointerClick, Pencil, Plus, Trash2 } from "lucide-react";
import Button from "../../components/common/Button";
import Select from "../../components/common/Select";
import Modal from "../../components/common/Modal";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import Pagination from "../../components/common/Pagination";
import DataTable from "../../components/tables/DataTable";
import TableToolbar from "../../components/tables/TableToolbar";
import Badge from "../../components/common/Badge";
import ErrorState from "../../components/common/ErrorState";
import BannerForm from "../../components/forms/BannerForm";
import { useListPage } from "../../hooks/useListPage";
import { useStore } from "../../context/StoreContext";
import { useNotification } from "../../context/NotificationContext";
import { bannerService } from "../../services/bannerService";
import { formatDate, formatNumber } from "../../utils/format";
import { BANNER_PLACEMENTS } from "../../utils/constants";

/** Home banners: create, edit, toggle live state, delete. */
export default function BannersPage() {
  const { dataVersion, bumpDataVersion } = useStore();
  const { notify } = useNotification();

  const list = useListPage(bannerService.list, { page_size: 20, ordering: "display_order" });
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [busyId, setBusyId] = useState(null);

  useEffect(() => { list.reload(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [dataVersion]);

  const toggle = async (row) => {
    setBusyId(row.id);
    try {
      await bannerService.toggle(row.id);
      notify.success(row.is_active ? "Banner hidden" : "Banner activated");
      list.reload();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not toggle this banner.");
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await bannerService.remove(deleteTarget.id);
      notify.success("Banner deleted");
      setDeleteTarget(null);
      list.reload();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not delete this banner.");
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    {
      key: "title",
      header: "Banner",
      sortable: true,
      render: (r) => (
        <div className="flex items-center gap-2.5">
          {r.image_url ? (
            <img src={r.image_url} alt="" className="h-10 w-16 shrink-0 rounded-lg object-cover" loading="lazy" />
          ) : (
            <span className="grid h-10 w-16 shrink-0 place-items-center rounded-lg bg-slate-100 text-[10px] text-slate-400">No image</span>
          )}
          <div className="min-w-0">
            <p className="font-semibold text-slate-900">{r.title}</p>
            <p className="truncate text-[11px] text-slate-500">{r.subtitle || r.alt_text || "—"}</p>
          </div>
        </div>
      ),
    },
    { key: "placement_display", header: "Placement", render: (r) => <Badge tone="indigo">{r.placement_display || r.placement}</Badge> },
    {
      key: "link",
      header: "Links to",
      render: (r) => (
        <span className="text-[11px] text-slate-600">
          {r.link_type === "none" ? "—" : r.resolved_link || r.link_url || r.link_type}
        </span>
      ),
    },
    {
      key: "window",
      header: "Schedule",
      render: (r) => (
        <span className="text-[11px] text-slate-600">
          {r.start_date || r.end_date ? `${formatDate(r.start_date)} → ${formatDate(r.end_date)}` : "Always"}
        </span>
      ),
    },
    {
      key: "stats",
      header: "Views / Clicks",
      align: "right",
      render: (r) => (
        <div className="text-[11px] text-slate-600">
          <p className="tabular-nums">{formatNumber(r.view_count)} views</p>
          <p className="inline-flex items-center gap-0.5 tabular-nums text-brand-700">
            <MousePointerClick className="h-3 w-3" aria-hidden="true" />{formatNumber(r.click_count)}
          </p>
        </div>
      ),
    },
    {
      key: "is_active",
      header: "State",
      render: (r) => (
        <div className="flex flex-wrap gap-1">
          <Badge tone={r.is_live ? "green" : r.is_active ? "amber" : "slate"}>
            {r.is_live ? "Live" : r.is_active ? "Scheduled" : "Hidden"}
          </Badge>
        </div>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => (
        <div className="flex justify-end gap-1">
          <button type="button" onClick={() => toggle(row)} disabled={busyId === row.id} title="Toggle visibility"
            className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-40">
            {row.is_active ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
            <span className="sr-only">Toggle {row.title}</span>
          </button>
          <button type="button" onClick={() => { setEditing(row); setFormOpen(true); }} title="Edit"
            className="rounded p-1.5 text-slate-500 hover:bg-brand-50 hover:text-brand-700">
            <Pencil className="h-4 w-4" aria-hidden="true" /><span className="sr-only">Edit {row.title}</span>
          </button>
          <button type="button" onClick={() => setDeleteTarget(row)} title="Delete"
            className="rounded p-1.5 text-slate-500 hover:bg-rose-50 hover:text-rose-700">
            <Trash2 className="h-4 w-4" aria-hidden="true" /><span className="sr-only">Delete {row.title}</span>
          </button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Banners</h1>
          <p className="mt-0.5 text-xs text-slate-500">The hero images customers see on the storefront.</p>
        </div>
        <Button onClick={() => { setEditing(null); setFormOpen(true); }} leftIcon={<Plus className="h-4 w-4" />}>New banner</Button>
      </div>

      <TableToolbar
        search={list.searchInput}
        onSearchChange={list.setSearch}
        searchPlaceholder="Banner title…"
        onRefresh={list.reload}
        refreshing={list.loading}
        filters={
          <>
            <Select aria-label="Filter by placement" value={list.filters.placement || ""} onChange={(e) => list.setFilter("placement", e.target.value)}
              options={[{ value: "", label: "All placements" }, ...BANNER_PLACEMENTS]} containerClassName="w-44" className="h-9" />
            <Select aria-label="Filter by active state" value={list.filters.is_active || ""} onChange={(e) => list.setFilter("is_active", e.target.value)}
              options={[{ value: "", label: "Any state" }, { value: "true", label: "Active" }, { value: "false", label: "Hidden" }]}
              containerClassName="w-36" className="h-9" />
          </>
        }
      />

      {list.error ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : (
        <>
          <DataTable columns={columns} rows={list.rows} loading={list.loading} sort={list.sort} onSortChange={list.setSort}
            emptyTitle="No banners" emptyDescription="Upload a hero image so the home page has something to show."
            emptyAction={<Button size="sm" onClick={() => { setEditing(null); setFormOpen(true); }} leftIcon={<Plus className="h-4 w-4" />}>New banner</Button>}
            caption="Banners" />
          <Pagination count={list.count} page={list.page} pageSize={list.pageSize}
            hasNext={list.hasNext} hasPrevious={list.hasPrevious} onPageChange={list.setPage} />
        </>
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? `Edit ${editing.title}` : "New banner"} size="lg">
        <BannerForm
          banner={editing}
          onSaved={() => { setFormOpen(false); list.reload(); bumpDataVersion(); }}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
        loading={deleting}
        title="Delete banner?"
        description={`"${deleteTarget?.title}" will be removed from the storefront immediately.`}
        confirmLabel="Delete banner"
      />
    </div>
  );
}
