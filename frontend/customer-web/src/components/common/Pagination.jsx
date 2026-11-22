/** Prev / page numbers / next. Renders nothing for a single page. */
export default function Pagination({ page, pageCount, onChange, className = "" }) {
  if (!pageCount || pageCount <= 1) return null;

  // Show at most 5 numbers around the current page.
  const start = Math.max(1, Math.min(page - 2, pageCount - 4));
  const pages = [];
  for (let p = start; p <= Math.min(pageCount, start + 4); p += 1) pages.push(p);

  const btn =
    "grid h-9 min-w-9 place-items-center rounded-lg px-2 text-sm font-semibold transition disabled:opacity-40";

  return (
    <nav className={`flex items-center justify-center gap-1.5 ${className}`} aria-label="Pagination">
      <button
        type="button"
        className={`${btn} bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50`}
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
      >
        Prev
      </button>
      {pages.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onChange(p)}
          aria-current={p === page ? "page" : undefined}
          className={`${btn} ${
            p === page
              ? "bg-brand-600 text-white"
              : "bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50"
          }`}
        >
          {p}
        </button>
      ))}
      <button
        type="button"
        className={`${btn} bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50`}
        onClick={() => onChange(page + 1)}
        disabled={page >= pageCount}
      >
        Next
      </button>
    </nav>
  );
}
