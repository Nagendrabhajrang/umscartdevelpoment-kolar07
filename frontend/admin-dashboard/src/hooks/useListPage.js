import { useCallback, useEffect, useRef, useState } from "react";
import { useDebounce } from "./useDebounce";

/**
 * Powers every table page in the dashboard: search, filters, sorting and
 * pagination all become query params, and a single `reload` re-fetches.
 *
 *   const list = useListPage(orderService.list, { page_size: 20 });
 *   list.rows, list.count, list.loading, list.error, list.search, list.setSearch,
 *   list.setFilter("status", "pending"), list.sort, list.setSort, list.page,
 *   list.setPage, list.reload()
 *
 * `fetcher` receives the merged query object and must return
 * { results, count, next, previous }.
 */
export function useListPage(fetcher, initial = {}, { debounce = 350 } = {}) {
  const { page_size = 20, ordering: initialOrdering = "-created_at", ...initialFilters } = initial;

  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [page, setPage] = useState(1);
  const [sort, setSort] = useState(initialOrdering);
  const [searchInput, setSearchInput] = useState("");
  const [filters, setFilters] = useState(initialFilters);

  const search = useDebounce(searchInput, debounce);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  /* Any search/filter/sort change returns to page 1. */
  useEffect(() => { setPage(1); }, [search, JSON.stringify(filters), sort]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const query = { page, page_size, ordering: sort, ...filters };
      if (search) query.search = search;
      Object.keys(query).forEach((k) => {
        if (query[k] === "" || query[k] === undefined || query[k] === null) delete query[k];
      });
      const result = await fetcherRef.current(query);
      if (!alive.current) return;
      setRows(result.results);
      setCount(result.count);
      setHasNext(Boolean(result.next));
      setHasPrevious(Boolean(result.previous));
    } catch (e) {
      if (alive.current) { setError(e); setRows([]); setCount(0); }
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [page, page_size, sort, search, filters]);

  useEffect(() => { load(); }, [load]);

  const setFilter = useCallback((key, value) => {
    setFilters((f) => {
      const next = { ...f };
      if (value === "" || value === undefined || value === null) delete next[key];
      else next[key] = value;
      return next;
    });
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(initialFilters);
    setSearchInput("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    rows, count, hasNext, hasPrevious, loading, error,
    page, setPage, pageSize: page_size,
    sort, setSort,
    search, searchInput, setSearch: setSearchInput,
    filters, setFilter, resetFilters,
    reload: load,
  };
}

export default useListPage;
