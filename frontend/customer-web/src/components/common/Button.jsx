/**
 * One button, four looks. `as="a"` renders an anchor for navigation so the
 * whole app never nests an <a> inside a <button>.
 */
const VARIANTS = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 active:bg-brand-800 shadow-sm",
  secondary: "bg-white text-slate-800 ring-1 ring-inset ring-slate-300 hover:bg-slate-50",
  ghost: "bg-transparent text-slate-700 hover:bg-slate-100",
  danger: "bg-rose-600 text-white hover:bg-rose-700 active:bg-rose-800",
};

const SIZES = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-12 px-6 text-base gap-2",
};

export default function Button({
  children,
  variant = "primary",
  size = "md",
  as: Tag = "button",
  className = "",
  loading = false,
  disabled = false,
  fullWidth = false,
  ...rest
}) {
  const base =
    "inline-flex items-center justify-center rounded-xl font-semibold transition-colors " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 " +
    "disabled:cursor-not-allowed disabled:opacity-50";
  const classes = [
    base,
    VARIANTS[variant] || VARIANTS.primary,
    SIZES[size] || SIZES.md,
    fullWidth ? "w-full" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  if (Tag === "button") {
    return (
      <button type="button" className={classes} disabled={disabled || loading} {...rest}>
        {loading ? <Spinner /> : null}
        {children}
      </button>
    );
  }
  return (
    <Tag className={classes} {...rest}>
      {children}
    </Tag>
  );
}

function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
    />
  );
}
