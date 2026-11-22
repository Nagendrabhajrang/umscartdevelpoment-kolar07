/** Busy indicator. `label` is read out, the ring is decoration. */
const SIZES = { sm: "h-4 w-4 border-2", md: "h-6 w-6 border-2", lg: "h-9 w-9 border-[3px]" };

export default function Spinner({ size = "md", label = "Loading" }) {
  return (
    <span className="inline-flex items-center gap-2" role="status" aria-live="polite">
      <span
        aria-hidden="true"
        className={`animate-spin rounded-full border-slate-300 border-t-brand-600 ${SIZES[size] || SIZES.md}`}
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
