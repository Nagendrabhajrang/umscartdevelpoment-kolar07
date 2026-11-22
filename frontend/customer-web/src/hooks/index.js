import { useCallback, useEffect, useRef, useState } from "react";
// Import, then export the SAME binding. `export { default as x } from "./x"`
// is a pure re-export: it does NOT create a local `x`. usePagedList below calls
// useDebounce directly, so the explicit import is what makes that work - and
// binding-then-exporting keeps a single source of truth for the name.
import useDebounce from "./useDebounce";
import useLocalStorage from "./useLocalStorage";
import useMediaQuery from "./useMediaQuery";
import useCountdown from "./useCountdown";

export { useDebounce, useLocalStorage, useMediaQuery, useCountdown };

/**
 * The single data-fetching hook used by every page.
 *
 * Deliberately minimal: a stable `reload`, an `alive` flag so a response that
 * arrives after unmount is ignored, and `data` cleared on error so a page can
 * never show stale rows next to an error banner.
 *
 *   const { data, loading, error, reload } = useFetch(() => cartService.getCart());
 */
export function useFetch(fetcher, deps = [], { skip = false } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(!skip);
  const [error, setError] = useState(null);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const alive = useRef(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    if (skip) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetcherRef
      .current()
      .then((result) => {
        if (alive.current) setData(result);
      })
      .catch((e) => {
        if (alive.current) {
          setError(e);
          setData(null);
        }
      })
      .finally(() => {
        if (alive.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, skip, ...deps]);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  return { data, loading, error, reload, setData };
}

/**
 * Paginated list with search, filter, sort and page — the customer-side twin of
 * the admin dashboard's useListPage. `fetcher` must return
 * `{ results, count, next, previous }`.
 */
export function usePagedList(fetcher, initial = {}) {
  const {
    page_size = 20,
    ordering: initialOrdering = "-created_at",
    debounce = 350,
    ...initialFilters
  } = initial;

  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
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
    return () => {
      alive.current = false;
    };
  }, []);

  // Any filter/search/sort change starts again from page 1.
  useEffect(() => {
    setPage(1);
  }, [search, JSON.stringify(filters), sort]);

  const [tick, setTick] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const query = { page, page_size, ordering: sort, ...filters };
    if (search) query.search = search;

    // Strip blank values BEFORE the request goes out. A present-but-empty
    // `category=` or `in_stock=` is parsed by django-filter as a real filter
    // value and matches nothing, which looks like "the catalogue is empty"
    // rather than "no filter applied".
    Object.keys(query).forEach((k) => {
      const v = query[k];
      if (v === "" || v === undefined || v === null || v === "undefined" || v === "null") {
        delete query[k];
      }
    });

    fetcherRef
      .current(query)
      .then((result) => {
        if (!alive.current) return;
        setRows(result?.results ?? []);
        setCount(result?.count ?? 0);
      })
      .catch((e) => {
        if (!alive.current) return;
        setError(e);
        setRows([]);
        setCount(0);
      })
      .finally(() => {
        if (alive.current) setLoading(false);
      });
  }, [page, sort, search, JSON.stringify(filters), page_size, tick]);

  const setFilter = useCallback((key, value) => {
    setFilters((f) => ({ ...f, [key]: value }));
  }, []);

  const pageCount = Math.max(1, Math.ceil(count / page_size));

  return {
    rows,
    count,
    loading,
    error,
    page,
    setPage,
    pageCount,
    pageSize: page_size,
    sort,
    setSort,
    search: searchInput,
    setSearch: setSearchInput,
    filters,
    setFilter,
    reload: () => setTick((t) => t + 1),
  };
}
