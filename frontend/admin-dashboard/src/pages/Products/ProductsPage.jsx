import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, Pencil, Plus, Trash2, PackagePlus } from "lucide-react";
import Button from "../../components/common/Button";
import Select from "../../components/common/Select";
import Modal from "../../components/common/Modal";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import Pagination from "../../components/common/Pagination";
import Badge, { OrderStatusBadge } from "../../components/common/Badge";
import DataTable from "../../components/tables/DataTable";
import TableToolbar from "../../components/tables/TableToolbar";
import StatusPill from "../../components/tables/StatusPill";
import ProductForm from "../../components/forms/ProductForm";
import StockAdjustForm from "../../components/forms/StockAdjustForm";
import ErrorState from "../../components/common/ErrorState";
import { useListPage } from "../../hooks/useListPage";
import { useStore } from "../../context/StoreContext";
import { useNotification } from "../../context/NotificationContext";
import { catalogService } from "../../services/catalogService";
import { inventoryService } from "../../services/inventoryService";
import { PRODUCT_STATUSES } from "../../utils/constants";
import { formatMoney, formatNumber, titleCase, downloadCsv } from "../../utils/format";

/**
 * Products list with full CRUD.
 * Stock is shown from the product record; the "restock" action opens the
 * inventory adjustment form, which writes an auditable movement.
 */
export default function ProductsPage() {
  const { dataVersion, bumpDataVersion } = useStore();
  const { notify } = useNotification();

  const list = useListPage(catalogService.getProducts, { page_size: 20, ordering: "-created_at" });
  const [categories, setCategories] = useState([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [stockTarget, setStockTarget] = useState(null);
  const [stockSummary, setStockSummary] = useState(null);
  const [statusCounts, setStatusCounts] = useState({});
  const [categoryView, setCategoryView] = useState("all"); // all | active | hidden

  const loadCategories = () => {
    catalogService.getAllCategories().then(setCategories).catch(() => setCategories([]));
  };
  const loadStockSummary = () => {
    inventoryService.summary().then(setStockSummary).catch(() => setStockSummary(null));
  };
  // There is no /products/stats/ route, so the status tally is four cheap
  // count-only queries (page_size=1 - we only read `count`).
  const loadStatusCounts = async () => {
    try {
      const rows = await Promise.all(
        PRODUCT_STATUSES.map((s2) =>
          catalogService
            .getProducts({ status: s2.value, page_size: 1 })
            .then((r) => [s2.value, r.count ?? 0])
            .catch(() => [s2.value, 0]),
        ),
      );
      setStatusCounts(Object.fromEntries(rows));
    } catch {
      setStatusCounts({});
    }
  };

  useEffect(() => { loadCategories(); loadStockSummary(); loadStatusCounts(); }, []);

  useEffect(() => {
    list.reload();
    loadCategories();
    loadStockSummary();
    loadStatusCounts();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [dataVersion]);

  const openNew = () => { setEditing(null); setFormOpen(true); };
  const openEdit = (product) => { setEditing(product); setFormOpen(true); };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await catalogService.deleteProduct(deleteTarget.id);
      notify.success(`${deleteTarget.name} deleted`);
      setDeleteTarget(null);
      list.reload();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not delete this product. It may be part of past orders.");
    } finally {
      setDeleting(false);
    }
  };

  const toggleFeatured = async (product) => {
    try {
      await catalogService.updateProduct(product.id, { is_featured: !product.is_featured });
      notify.success(product.is_featured ? "Removed from featured" : "Marked as featured");
      list.reload();
    } catch (e) {
      notify.error(e.message || "Could not update the product.");
    }
  };

  const openRestock = async (product) => {
    // The adjustment form needs the stock row, not the product row.
    try {
      const stockPage = await inventoryService.listStock({ product: product.id, page_size: 1 });
      const stock = stockPage.results[0];
      if (!stock) {
        // No stock row yet - create one with zero so it can be restocked.
        const created = await inventoryService.createStock({ product: product.id, quantity: 0, track_inventory: true });
        setStockTarget(created);
      } else {
        setStockTarget(stock);
      }
    } catch (e) {
      notify.error(e.message || "Could not open the stock record for this product.");
    }
  };

  const columns = [
    {
      key: "name",
      header: "Product",
      sortable: true,
      render: (row) => (
        <div className="flex items-center gap-2.5">
          {row.image_url ? (
            <img src={row.image_url} alt="" className="h-9 w-9 shrink-0 rounded-lg object-cover" loading="lazy" />
          ) : (
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-xs font-bold text-slate-400">
              {row.name?.[0]}
            </span>
          )}
          <div className="min-w-0">
            <Link to={`/products/${row.id}`} className="line-clamp-1 font-semibold text-slate-900 hover:text-brand-700">
              {row.name}
            </Link>
            <p className="truncate text-[11px] text-slate-500">{row.sku} · {row.unit_label}</p>
          </div>
        </div>
      ),
    },
    { key: "category_name", header: "Category", render: (r) => <span className="text-xs text-slate-600">{r.category_name}</span> },
    {
      key: "selling_price",
      header: "Price",
      sortable: true,
      align: "right",
      render: (r) => (
        <div>
          <p className="font-semibold text-slate-900">{formatMoney(r.selling_price)}</p>
          {Number(r.mrp) > Number(r.selling_price) && (
            <p className="text-[11px] text-slate-400 line-through">{formatMoney(r.mrp)}</p>
          )}
        </div>
      ),
    },
    {
      key: "discount_percent",
      header: "Disc.",
      sortable: true,
      align: "right",
      render: (r) => (Number(r.discount_percent) > 0
        ? <Badge tone="green">{Math.round(Number(r.discount_percent))}%</Badge>
        : <span className="text-xs text-slate-400">—</span>),
    },
    {
      key: "available_quantity",
      header: "Stock",
      sortable: true,
      align: "right",
      render: (r) => {
        const qty = r.available_quantity ?? 0;
        const tone = qty <= 0 ? "text-rose-600" : qty <= 5 ? "text-amber-600" : "text-slate-700";
        return <span className={`text-sm font-semibold ${tone}`}>{formatNumber(qty)}</span>;
      },
    },
    {
      key: "status",
      header: "Status",
      render: (r) => (
        <div className="flex flex-wrap gap-1">
          <Badge tone={r.status === "active" ? "green" : r.status === "draft" ? "amber" : r.status === "discontinued" ? "red" : "slate"}>
            {titleCase(r.status)}
          </Badge>
          {r.is_featured && <Badge tone="violet">Featured</Badge>}
        </div>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => (
        <div className="flex items-center justify-end gap-1">
          <button type="button" onClick={() => openRestock(row)} title="Adjust stock"
            className="rounded p-1.5 text-slate-500 hover:bg-emerald-50 hover:text-emerald-700">
            <PackagePlus className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">Adjust stock for {row.name}</span>
          </button>
          <button type="button" onClick={() => toggleFeatured(row)} title="Toggle featured"
            className="rounded p-1.5 text-slate-500 hover:bg-violet-50 hover:text-violet-700">
            <Eye className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">Toggle featured for {row.name}</span>
          </button>
          <button type="button" onClick={() => openEdit(row)} title="Edit"
            className="rounded p-1.5 text-slate-500 hover:bg-brand-50 hover:text-brand-700">
            <Pencil className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">Edit {row.name}</span>
          </button>
          <button type="button" onClick={() => setDeleteTarget(row)} title="Delete"
            className="rounded p-1.5 text-slate-500 hover:bg-rose-50 hover:text-rose-700">
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">Delete {row.name}</span>
          </button>
        </div>
      ),
    },
  ];

  // Category visibility. `is_active` is the flag that hides a category from the
  // storefront, so that is what "Active" / "Hidden" mean here.
  const categoryActive = categories.filter((c) => c.is_active).length;
  const categoryHidden = categories.length - categoryActive;

  // Which bucket of categories the strip is showing.
  const visibleCategories = categories.filter((c) => {
    if (categoryView === "active") return c.is_active;
    if (categoryView === "hidden") return !c.is_active;
    return true;
  });

  const STATUS_TONES = {
    active: "border-emerald-200 bg-emerald-50 text-emerald-900",
    inactive: "border-slate-300 bg-slate-100 text-slate-700",
    draft: "border-sky-200 bg-sky-50 text-sky-900",
    discontinued: "border-rose-200 bg-rose-50 text-rose-900",
  };

  // Card filters. "All" clears the category; clicking a card again clears it.
  const activeCategory = list.filters.category || "";
  const pickCategory = (id) => {
    const next = String(id);
    list.setFilter("category", activeCategory === next ? "" : next);
  };
  const pickStock = (value) => {
    list.setFilter("in_stock", list.filters.in_stock === value ? "" : value);
  };

  const stockCards = [
    {
      key: "all",
      label: "All products",
      value: stockSummary?.total_products,
      sub: stockSummary ? `${formatNumber(stockSummary.total_units)} units` : "—",
      tone: "border-slate-200 bg-white text-slate-900",
      chip: "bg-slate-100 text-slate-600",
      filter: "",
      dot: "bg-slate-400",
    },
    {
      key: "in",
      label: "In stock",
      value: stockSummary ? Math.max(0, (stockSummary.total_products ?? 0) - (stockSummary.out_of_stock ?? 0)) : null,
      sub: "available to sell",
      tone: "border-emerald-200 bg-emerald-50 text-emerald-900",
      chip: "bg-emerald-100 text-emerald-700",
      filter: "true",
      dot: "bg-emerald-500",
    },
    {
      key: "low",
      label: "Low stock",
      value: stockSummary?.low_stock,
      sub: "at or below threshold",
      tone: "border-amber-200 bg-amber-50 text-amber-900",
      chip: "bg-amber-100 text-amber-700",
      filter: "low",
      dot: "bg-amber-500",
    },
    {
      key: "out",
      label: "Out of stock",
      value: stockSummary?.out_of_stock,
      sub: "need restocking",
      tone: "border-rose-200 bg-rose-50 text-rose-900",
      chip: "bg-rose-100 text-rose-700",
      filter: "false",
      dot: "bg-rose-500",
    },
  ];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Products</h1>
          <p className="mt-0.5 text-xs text-slate-500">{formatNumber(list.count)} products in the catalog</p>
        </div>
        <Button onClick={openNew} leftIcon={<Plus className="h-4 w-4" />}>New product</Button>
      </div>

      {/* Stock cards — click to filter the table below. */}
      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {stockCards.map((c) => {
          const active = (list.filters.in_stock || "") === c.filter && (c.filter !== "" || !activeCategory);
          const isClickable = c.filter !== "" || activeCategory;
          return (
            <button
              key={c.key}
              type="button"
              disabled={!isClickable}
              onClick={() => pickStock(c.filter)}
              className={`rounded-xl border p-3 text-left transition ${c.tone} ${
                active ? "ring-2 ring-brand-500 ring-offset-1" : ""
              } ${isClickable ? "hover:brightness-[0.98]" : "cursor-default"}`}
              aria-pressed={active}
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
          );
        })}
      </div>

      {/* Status cards — click to filter by product status. */}
      <div className="mb-3">
        <h2 className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-500">
          Status
        </h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <button
            type="button"
            onClick={() => list.setFilter("status", "")}
            aria-pressed={!list.filters.status}
            className={`rounded-xl border p-2.5 text-left transition ${
              !list.filters.status
                ? "border-brand-500 bg-brand-50 text-brand-800 ring-1 ring-brand-500"
                : "border-slate-200 bg-white text-slate-900 hover:bg-slate-50"
            }`}
          >
            <p className="text-[10px] font-bold uppercase tracking-wide opacity-60">All</p>
            <p className="mt-0.5 text-lg font-extrabold leading-none">{formatNumber(list.count)}</p>
          </button>
          {PRODUCT_STATUSES.map((st) => {
            const active = list.filters.status === st.value;
            const tone = STATUS_TONES[st.value] || "border-slate-200 bg-white text-slate-900";
            return (
              <button
                key={st.value}
                type="button"
                onClick={() => list.setFilter("status", active ? "" : st.value)}
                aria-pressed={active}
                className={`rounded-xl border p-2.5 text-left transition ${tone} ${
                  active ? "ring-2 ring-brand-500 ring-offset-1" : "hover:brightness-[0.98]"
                }`}
              >
                <p className="text-[10px] font-bold uppercase tracking-wide opacity-60">{st.label}</p>
                <p className="mt-0.5 text-lg font-extrabold leading-none">
                  {statusCounts[st.value] == null ? "—" : formatNumber(statusCounts[st.value])}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Category cards — every category, horizontally scrollable, counts included. */}
      <div className="mb-3">
        <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
            Categories ({categories.length})
          </h2>
          <div className="flex items-center gap-1.5">
            {[
              { key: "all", label: "All", count: categories.length, on: "bg-slate-800 text-white", off: "bg-white text-slate-600 ring-1 ring-slate-200" },
              { key: "active", label: "Active", count: categoryActive, on: "bg-emerald-600 text-white", off: "bg-white text-emerald-700 ring-1 ring-emerald-200" },
              { key: "hidden", label: "Hidden", count: categoryHidden, on: "bg-slate-500 text-white", off: "bg-white text-slate-500 ring-1 ring-slate-200" },
            ].map((v) => (
              <button
                key={v.key}
                type="button"
                onClick={() => setCategoryView(v.key)}
                aria-pressed={categoryView === v.key}
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                  categoryView === v.key ? v.on : v.off
                }`}
              >
                {v.label}
                <span className={`rounded-full px-1 text-[10px] ${
                  categoryView === v.key ? "bg-white/25" : "bg-slate-100 text-slate-600"
                }`}>{v.count}</span>
              </button>
            ))}
            {activeCategory && (
              <button
                type="button"
                onClick={() => list.setFilter("category", "")}
                className="text-[11px] font-semibold text-brand-700 hover:underline"
              >
                Clear filter
              </button>
            )}
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
          <button
            type="button"
            onClick={() => list.setFilter("category", "")}
            className={`shrink-0 rounded-xl border px-3 py-2 text-left transition ${
              !activeCategory
                ? "border-brand-500 bg-brand-50 text-brand-800 ring-1 ring-brand-500"
                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            <p className="text-xs font-bold">All</p>
            <p className="mt-0.5 text-[11px] text-slate-500">{formatNumber(list.count)} products</p>
          </button>
          {visibleCategories.map((c) => {
            const active = activeCategory === String(c.id);
            const count = c.product_count ?? 0;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => pickCategory(c.id)}
                className={`shrink-0 rounded-xl border px-3 py-2 text-left transition ${
                  active
                    ? "border-brand-500 bg-brand-50 text-brand-800 ring-1 ring-brand-500"
                    : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                <p className="max-w-[13ch] truncate text-xs font-bold" title={c.name}>{c.name}</p>
                <p className="mt-0.5 text-[11px] text-slate-500">
                  {count} {count === 1 ? "product" : "products"}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      <TableToolbar
        search={list.searchInput}
        onSearchChange={list.setSearch}
        searchPlaceholder="Search by name, SKU or brand…"
        onRefresh={list.reload}
        refreshing={list.loading}
        onExport={() => downloadCsv("products.csv", list.rows, ["id", "name", "sku", "category_name", "mrp", "selling_price", "available_quantity", "status"])}
        filters={
          <>
            <Select
              aria-label="Filter by category"
              value={list.filters.category || ""}
              onChange={(e) => list.setFilter("category", e.target.value)}
              options={[{ value: "", label: "All categories" }, ...categories.map((c) => ({ value: String(c.id), label: c.name }))]}
              containerClassName="w-44"
              className="h-9"
            />
            <Select
              aria-label="Filter by status"
              value={list.filters.status || ""}
              onChange={(e) => list.setFilter("status", e.target.value)}
              options={[{ value: "", label: "Any status" }, ...PRODUCT_STATUSES]}
              containerClassName="w-36"
              className="h-9"
            />
            <Select
              aria-label="Filter by stock"
              value={list.filters.in_stock || ""}
              onChange={(e) => list.setFilter("in_stock", e.target.value)}
              options={[{ value: "", label: "Any stock" }, { value: "true", label: "In stock" }, { value: "false", label: "Out of stock" }]}
              containerClassName="w-36"
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
            emptyTitle="No products match"
            emptyDescription="Try clearing the filters, or create your first product."
            emptyAction={<Button size="sm" onClick={openNew} leftIcon={<Plus className="h-4 w-4" />}>New product</Button>}
            caption="Products"
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

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? `Edit ${editing.name}` : "New product"}
        size="xl"
      >
        <ProductForm
          product={editing}
          categories={categories}
          onSaved={() => { setFormOpen(false); list.reload(); bumpDataVersion(); }}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <Modal
        open={Boolean(stockTarget)}
        onClose={() => setStockTarget(null)}
        title="Adjust stock"
        size="sm"
      >
        {stockTarget && (
          <StockAdjustForm
            stock={stockTarget}
            mode="add"
            onSaved={() => { setStockTarget(null); list.reload(); bumpDataVersion(); }}
            onCancel={() => setStockTarget(null)}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
        loading={deleting}
        title="Delete product?"
        description={`"${deleteTarget?.name}" will be removed from the catalog. Products already in past orders keep their historical records.`}
        confirmLabel="Delete product"
      />
    </div>
  );
}
