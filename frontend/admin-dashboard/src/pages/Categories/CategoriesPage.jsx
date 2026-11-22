import { useEffect, useState } from "react";
import { Plus, Trash2, Pencil } from "lucide-react";
import Button from "../../components/common/Button";
import Select from "../../components/common/Select";
import Modal from "../../components/common/Modal";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import Pagination from "../../components/common/Pagination";
import DataTable from "../../components/tables/DataTable";
import TableToolbar from "../../components/tables/TableToolbar";
import ErrorState from "../../components/common/ErrorState";
import CategoryForm from "../../components/forms/CategoryForm";
import { useListPage } from "../../hooks/useListPage";
import { useStore } from "../../context/StoreContext";
import { useNotification } from "../../context/NotificationContext";
import { catalogService } from "../../services/catalogService";
import { formatNumber } from "../../utils/format";

/** Category management. Parent/child tree shown as a flat list with a level. */
export default function CategoriesPage() {
  const { dataVersion, bumpDataVersion } = useStore();
  const { notify } = useNotification();

  const list = useListPage(catalogService.getCategories, { page_size: 100, ordering: "display_order" });
  const [allCategories, setAllCategories] = useState([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [showEmptyOnly, setShowEmptyOnly] = useState(false);

  const loadAll = () => catalogService.getAllCategories().then(setAllCategories).catch(() => setAllCategories([]));

  useEffect(() => { loadAll(); }, [dataVersion]);

  const openNew = () => { setEditing(null); setFormOpen(true); };
  const openEdit = (row) => { setEditing(row); setFormOpen(true); };

  const toggleActive = async (row) => {
    try {
      await catalogService.updateCategory(row.id, { is_active: !row.is_active });
      notify.success(row.is_active ? `${row.name} hidden` : `${row.name} activated`);
      list.reload();
      loadAll();
    } catch (e) {
      notify.error(e.message || "Could not update the category.");
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await catalogService.deleteCategory(deleteTarget.id);
      notify.success(`${deleteTarget.name} deleted`);
      setDeleteTarget(null);
      list.reload();
      loadAll();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Cannot delete a category that still has products or sub-categories.");
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    {
      key: "name",
      header: "Category",
      sortable: true,
      render: (row) => (
        <div className="flex items-center gap-2.5">
          {row.image ? (
            <img src={row.image} alt="" className="h-8 w-8 rounded-full object-cover" loading="lazy" />
          ) : (
            <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-50 text-[10px] font-bold text-brand-700">
              {row.name?.slice(0, 2).toUpperCase()}
            </span>
          )}
          <div>
            <p className="font-semibold text-slate-900">
              {row.parent && <span className="mr-1 text-slate-300">└</span>}
              {row.name}
            </p>
            <p className="text-[11px] text-slate-500">{row.full_path || row.slug}</p>
          </div>
        </div>
      ),
    },
    { key: "parent_name", header: "Parent", render: (r) => <span className="text-xs text-slate-600">{r.parent_name || "—"}</span> },
    { key: "product_count", header: "Products", sortable: true, align: "right", render: (r) => <span className="font-semibold text-slate-800">{r.product_count}</span> },
    { key: "display_order", header: "Order", align: "right", render: (r) => <span className="text-xs text-slate-500">{r.display_order ?? 0}</span> },
    {
      key: "is_active",
      header: "Active",
      render: (r) => (
        <button
          type="button"
          onClick={() => toggleActive(r)}
          aria-pressed={r.is_active}
          className={`rounded-full px-2 py-0.5 text-[11px] font-semibold transition ${r.is_active ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-200" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
        >
          {r.is_active ? "Active" : "Hidden"}
        </button>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => (
        <div className="flex justify-end gap-1">
          <button type="button" onClick={() => openEdit(row)} className="rounded p-1.5 text-slate-500 hover:bg-brand-50 hover:text-brand-700" title="Edit">
            <Pencil className="h-4 w-4" aria-hidden="true" /><span className="sr-only">Edit {row.name}</span>
          </button>
          <button type="button" onClick={() => setDeleteTarget(row)} className="rounded p-1.5 text-slate-500 hover:bg-rose-50 hover:text-rose-700" title="Delete">
            <Trash2 className="h-4 w-4" aria-hidden="true" /><span className="sr-only">Delete {row.name}</span>
          </button>
        </div>
      ),
    },
  ];

  // Card counts. allCategories is already loaded for the sidebar tree, so
  // these are free - no extra requests.
  const totalCategories = allCategories.length;
  const activeCount = allCategories.filter((c) => c.is_active).length;
  const hiddenCount = totalCategories - activeCount;
  const topLevelCount = allCategories.filter((c) => !c.parent).length;
  const subCount = allCategories.filter((c) => c.parent).length;
  const emptyCount = allCategories.filter((c) => (c.product_count ?? 0) === 0).length;

  const stateFilter = list.filters.is_active || ""; // "" | "true" | "false"

  const categoryCards = [
    {
      key: "all",
      label: "All categories",
      value: totalCategories,
      sub: `${topLevelCount} top level · ${subCount} sub`,
      tone: "border-slate-200 bg-white text-slate-900",
      dot: "bg-slate-400",
      onClick: () => { setShowEmptyOnly(false); list.setFilter("is_active", ""); },
      active: stateFilter === "",
    },
    {
      key: "active",
      label: "Active",
      value: activeCount,
      sub: "visible in the store",
      tone: "border-emerald-200 bg-emerald-50 text-emerald-900",
      dot: "bg-emerald-500",
      onClick: () => { setShowEmptyOnly(false); list.setFilter("is_active", stateFilter === "true" ? "" : "true"); },
      active: stateFilter === "true",
    },
    {
      key: "hidden",
      label: "Hidden",
      value: hiddenCount,
      sub: "not shown to customers",
      tone: "border-slate-300 bg-slate-100 text-slate-700",
      dot: "bg-slate-500",
      onClick: () => { setShowEmptyOnly(false); list.setFilter("is_active", stateFilter === "false" ? "" : "false"); },
      active: stateFilter === "false",
    },
    {
      key: "empty",
      label: "Empty",
      value: emptyCount,
      sub: "no products yet",
      tone: "border-amber-200 bg-amber-50 text-amber-900",
      dot: "bg-amber-500",
      onClick: () => {
        // No server filter for "no products" - filter the loaded rows locally.
        list.setFilter("is_active", "");
        setShowEmptyOnly((v) => !v);
      },
      active: showEmptyOnly,
    },
  ];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Categories</h1>
          <p className="mt-0.5 text-xs text-slate-500">
            {allCategories.length} categories · {allCategories.filter((c) => c.parent).length} sub-categories
          </p>
        </div>
        <Button onClick={openNew} leftIcon={<Plus className="h-4 w-4" />}>New category</Button>
      </div>

      {/* State cards — each one filters the table below. */}
      <div className="mb-3 grid grid-cols-2 gap-2 lg:grid-cols-4">
        {categoryCards.map((c) => (
          <button
            key={c.key}
            type="button"
            onClick={c.onClick}
            aria-pressed={c.active}
            className={`rounded-xl border p-3 text-left transition ${c.tone} ${
              c.active ? "ring-2 ring-brand-500 ring-offset-1" : "hover:brightness-[0.98]"
            }`}
          >
            <div className="flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} aria-hidden="true" />
              <span className="text-[11px] font-bold uppercase tracking-wide opacity-70">{c.label}</span>
            </div>
            <p className="mt-1 text-2xl font-extrabold leading-none">
              {c.value == null ? "—" : formatNumber(c.value)}
            </p>
            <p className="mt-1 text-[11px] opacity-70">{c.sub}</p>
          </button>
        ))}
      </div>

      <TableToolbar
        search={list.searchInput}
        onSearchChange={list.setSearch}
        searchPlaceholder="Search categories…"
        onRefresh={list.reload}
        refreshing={list.loading}
        filters={
          <Select
            aria-label="Filter by active state"
            value={list.filters.is_active || ""}
            onChange={(e) => list.setFilter("is_active", e.target.value)}
            options={[{ value: "", label: "Any state" }, { value: "true", label: "Active only" }, { value: "false", label: "Hidden only" }]}
            containerClassName="w-40"
            className="h-9"
          />
        }
      />

      {list.error ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={showEmptyOnly ? list.rows.filter((r) => (r.product_count ?? 0) === 0) : list.rows}
            loading={list.loading}
            sort={list.sort}
            onSortChange={list.setSort}
            emptyTitle="No categories"
            emptyDescription="Create categories so products can be grouped."
            emptyAction={<Button size="sm" onClick={openNew} leftIcon={<Plus className="h-4 w-4" />}>New category</Button>}
            caption="Categories"
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

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? `Edit ${editing.name}` : "New category"} size="lg">
        <CategoryForm
          category={editing}
          categories={allCategories}
          onSaved={() => { setFormOpen(false); list.reload(); loadAll(); bumpDataVersion(); }}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
        loading={deleting}
        title="Delete category?"
        description={`"${deleteTarget?.name}" will be removed. A category that still has products or sub-categories cannot be deleted — move them first.`}
        confirmLabel="Delete category"
      />
    </div>
  );
}
