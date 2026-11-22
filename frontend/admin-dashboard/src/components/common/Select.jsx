import { forwardRef, useId } from "react";
import clsx from "clsx";
import { ChevronDown } from "lucide-react";

const Select = forwardRef(function Select(
  { label, error, options = [], placeholder, required, className = "", containerClassName = "", id, children, ...rest },
  ref,
) {
  const autoId = useId();
  const selectId = id || `sel-${autoId}`;
  return (
    <div className={clsx("w-full", containerClassName)}>
      {label && (
        <label htmlFor={selectId} className="mb-1 block text-xs font-semibold text-slate-600">
          {label}
          {required && <span className="ml-0.5 text-rose-500" aria-hidden="true">*</span>}
        </label>
      )}
      <div className="relative">
        <select
          ref={ref}
          id={selectId}
          aria-invalid={Boolean(error)}
          className={clsx(
            "h-10 w-full appearance-none rounded-lg border bg-white px-3 pr-8 text-sm text-slate-900 focus:outline-none focus:ring-2",
            error ? "border-rose-400 focus:ring-rose-100" : "border-slate-300 focus:border-brand-500 focus:ring-brand-100",
            className,
          )}
          {...rest}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {children || options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
      </div>
      {error && <p role="alert" className="mt-1 text-xs font-medium text-rose-600">{error}</p>}
    </div>
  );
});

export default Select;
