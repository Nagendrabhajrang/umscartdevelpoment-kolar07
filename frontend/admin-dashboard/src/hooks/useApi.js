import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Fetch-on-mount helper with the three states every screen needs.
 *
 *   const { data, loading, error, refetch } = useApi(
 *     () => catalogService.getProducts(params),
 *     [params],
 *   );
 *
 * `deps` behaves like a useEffect dependency list. The fetcher is held in a
 * ref so callers can pass an inline arrow function without causing a loop.
 */
export function useApi(fetcher, deps = [], options = {}) {
  const { immediate = true, initialData = null } = options;
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState(null);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  const run = useCallback(async (arg) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcherRef.current(arg);
      if (alive.current) setData(result);
      return result;
    } catch (e) {
      if (alive.current) setError(e);
      return null;
    } finally {
      if (alive.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (immediate) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, refetch: run, setData };
}

export default useApi;
