import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { usePagedList } from "../../hooks";
import { catalogService } from "../../services/catalogService";
import ProductGrid from "../../components/product/ProductGrid";
import ProductFilters from "../../components/product/ProductFilters";
import Pagination from "../../components/common/Pagination";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import Button from "../../components/common/Button";

/** Category-filtered product listing with sort, stock filter and paging. */
export default function ProductsPage() {
  const [params, setParams] = useSearchParams();
  const [categories, setCategories] = useState([]);
  const [filters, setFilters] = useState({
    category: params.get("category") || "",
    ordering: params.get("ordering") || "display_order",
    in_stock: params.get("in_stock") || "",
  });

  const list = usePagedList(catalogService.getProducts, {
    page_size: 20,
    ordering: filters.ordering,
    category: filters.category,
    in_stock: filters.in_stock,
  });

  useEffect(() => {
    catalogService.getAllCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  // Mirror the filter state into the URL so a filtered view is shareable.
  useEffect(() => {
    const next = {};
    if (filters.category) next.category = filters.category;
    if (filters.ordering && filters.ordering !== "display_order") next.ordering = filters.ordering;
    if (filters.in_stock) next.in_stock = filters.in_stock;
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const apply = (next) => {
    setFilters(next);
    list.setFilter("category", next.category);
    list.setFilter("in_stock", next.in_stock);
    list.setSort(next.ordering);
  };

  return (
    <div className="container-page py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">All products</h1>
        <p className="mt-1 text-sm text-slate-600">
          Fresh produce, pantry staples and everyday needs.
        </p>
      </header>

      <ProductFilters
        categories={categories}
        value={filters}
        onChange={apply}
        count={list.loading ? undefined : list.count}
      />

      <div className="mt-5">
        {list.error ? (
          <ErrorState error={list.error} onRetry={list.reload} title="Products did not load" />
        ) : (
          <ProductGrid
            products={list.rows}
            loading={list.loading}
            skeletonCount={10}
            empty={
              <EmptyState
                title="No products match those filters"
                description="Try a different category, or clear the filters to see everything."
                action={
                  <Button
                    variant="secondary"
                    onClick={() => apply({ category: "", ordering: "display_order", in_stock: "" })}
                  >
                    Clear filters
                  </Button>
                }
              />
            }
          />
        )}
      </div>

      <Pagination page={list.page} pageCount={list.pageCount} onChange={list.setPage} className="mt-8" />
    </div>
  );
}
