import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import useDebounce from "../../hooks/useDebounce";

/**
 * Header search. Submits on Enter or after a pause, and always navigates to
 * /search?q= — there is no inline suggestion list to keep in sync.
 */
export default function SearchBar({ initial = "", className = "", onSubmitQuery }) {
  const [value, setValue] = useState(initial);
  const navigate = useNavigate();
  const debounced = useDebounce(value, 500);

  useEffect(() => {
    setValue(initial);
  }, [initial]);

  // Live-filter only when a callback is supplied (search page); the header
  // version waits for an explicit submit.
  useEffect(() => {
    if (onSubmitQuery) onSubmitQuery(debounced.trim());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const submit = (e) => {
    e.preventDefault();
    const q = value.trim();
    if (q) navigate(`/search?q=${encodeURIComponent(q)}`);
  };

  return (
    <form onSubmit={submit} role="search" className={`relative ${className}`}>
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" strokeLinecap="round" />
      </svg>
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search products"
        aria-label="Search products"
        className="h-10 w-full rounded-xl border border-slate-300 bg-slate-50 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
      />
    </form>
  );
}
