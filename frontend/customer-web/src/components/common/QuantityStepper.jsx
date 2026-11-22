/** − / count / + control. Disables the minus at 1 unless `allowRemove`. */
export default function QuantityStepper({
  value = 1,
  onChange,
  min = 1,
  max = 99,
  disabled = false,
  size = "md",
}) {
  const h = size === "sm" ? "h-8 w-8" : "h-9 w-9";
  const minusDisabled = disabled || value <= min;

  return (
    <div className="inline-flex items-center rounded-xl bg-brand-600 text-white">
      <button
        type="button"
        onClick={() => onChange(Math.max(min - (min === 1 ? 0 : 1), value - 1))}
        disabled={minusDisabled}
        aria-label="Decrease quantity"
        className={`grid ${h} place-items-center rounded-l-xl text-lg font-bold leading-none transition hover:bg-brand-700 disabled:opacity-40`}
      >
        −
      </button>
      <span
        className="min-w-8 text-center text-sm font-bold tabular-nums"
        aria-live="polite"
        aria-label={`Quantity ${value}`}
      >
        {value}
      </span>
      <button
        type="button"
        onClick={() => onChange(Math.min(max, value + 1))}
        disabled={disabled || value >= max}
        aria-label="Increase quantity"
        className={`grid ${h} place-items-center rounded-r-xl text-lg font-bold leading-none transition hover:bg-brand-700 disabled:opacity-40`}
      >
        +
      </button>
    </div>
  );
}
