import { forwardRef } from "react";
import clsx from "clsx";
import { Loader2 } from "lucide-react";

const VARIANTS = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-300",
  secondary: "bg-slate-100 text-slate-800 hover:bg-slate-200",
  outline: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  danger: "bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-300",
  success: "bg-emerald-600 text-white hover:bg-emerald-700",
  warning: "bg-amber-500 text-white hover:bg-amber-600",
};

const SIZES = {
  xs: "h-7 px-2 text-xs gap-1",
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-11 px-5 text-sm gap-2",
  icon: "h-9 w-9",
};

const Button = forwardRef(function Button(
  { children, variant = "primary", size = "md", loading = false, disabled = false,
    leftIcon, rightIcon, className = "", type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center rounded-lg font-semibold transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-70",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600",
        VARIANTS[variant], SIZES[size], className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  );
});

export default Button;
