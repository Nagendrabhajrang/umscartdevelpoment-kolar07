import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { usePagedList } from "../../hooks";
import { catalogService } from "../../services/catalogService";
import ProductGrid from "../../components/product/ProductGrid";
import Pagination from "../../components/common/Pagination";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import SearchBar from "../../components/common/SearchBar";

/** Search results. The query lives in the URL so results are bookmarkable. */
export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") || "";
  const [term, setTerm] = useState(query);

  const list = usePagedList(
    (q) => catalogService.getProducts({ ...q, search: term }),
    { page_size: 20, ordering: "display_order" },
  );

  useEffect(() => {
    setTerm(query);
  }, [query]);

  const runSearch = (value) => {
    setTerm(value);
    setParams(value ? { q: value } : {}, { replace: true });
  };

  return (
    <div className="container-page py-6">
      <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Search</h1>
      <p className="mt-1 text-sm text-slate-600">
        {query ? `Results for “${query}”` : "Find anything in the store."}
      </p>

      <div className="mt-4 max-w-xl">
        <SearchBar initial={query} onSubmitQuery={runSearch} />
      </div>

      <div className="mt-5">
        {list.error ? (
          <ErrorState error={list.error} onRetry={list.reload} title="Search failed" />
        ) : !term ? (
          <EmptyState
            title="Start typing to search"
            description="Try “milk”, “atta”, “coffee” or a brand name."
          />
        ) : (
          <ProductGrid
            products={list.rows}
            loading={list.loading}
            skeletonCount={10}
            empty={
              <EmptyState
                title={`Nothing found for “${term}”`}
                description="Check the spelling, or browse the full catalogue instead."
              />
            }
          />
        )}
      </div>

      <Pagination page={list.page} pageCount={list.pageCount} onChange={list.setPage} className="mt-8" />
    </div>
  );
}
