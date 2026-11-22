import { forwardRef, useId } from "react";
import clsx from "clsx";

const Input = forwardRef(function Input(
  { label, error, hint, required, leftIcon, className = "", containerClassName = "", id, ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id || `in-${autoId}`;
  return (
    <div className={clsx("w-full", containerClassName)}>
      {label && (
        <label htmlFor={inputId} className="mb-1 block text-xs font-semibold text-slate-600">
          {label}
          {required && <span className="ml-0.5 text-rose-500" aria-hidden="true">*</span>}
        </label>
      )}
      <div className="relative">
        {leftIcon && <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400">{leftIcon}</span>}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={Boolean(error)}
          aria-required={required}
          className={clsx(
            "h-10 w-full rounded-lg border bg-white px-3 text-sm text-slate-900 transition placeholder:text-slate-400",
            "focus:outline-none focus:ring-2",
            leftIcon && "pl-8",
            error ? "border-rose-400 focus:border-rose-500 focus:ring-rose-100"
                  : "border-slate-300 focus:border-brand-500 focus:ring-brand-100",
            className,
          )}
          {...rest}
        />
      </div>
      {error && <p role="alert" className="mt-1 text-xs font-medium text-rose-600">{error}</p>}
      {!error && hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
});

export default Input;
