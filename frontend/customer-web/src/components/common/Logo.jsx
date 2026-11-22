import { Link } from "react-router-dom";

/** Wordmark. The mark is inline SVG so it needs no asset request. */
export default function Logo({ className = "", to = "/" }) {
  return (
    <Link to={to} className={`inline-flex items-center gap-2 ${className}`} aria-label="UMS Mart home">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-600 text-white shadow-sm">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" strokeLinejoin="round" />
          <path d="M3 6h18M16 10a4 4 0 0 1-8 0" strokeLinecap="round" />
        </svg>
      </span>
      <span className="text-lg font-extrabold tracking-tight text-slate-900">
        UMS<span className="text-brand-600">Mart</span>
      </span>
    </Link>
  );
}
