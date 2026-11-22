import { forwardRef, useId } from "react";
import clsx from "clsx";

const Textarea = forwardRef(function Textarea(
  { label, error, hint, required, rows = 3, className = "", containerClassName = "", id, ...rest },
  ref,
) {
  const autoId = useId();
  const areaId = id || `ta-${autoId}`;
  return (
    <div className={clsx("w-full", containerClassName)}>
      {label && (
        <label htmlFor={areaId} className="mb-1 block text-xs font-semibold text-slate-600">
          {label}
          {required && <span className="ml-0.5 text-rose-500" aria-hidden="true">*</span>}
        </label>
      )}
      <textarea
        ref={ref}
        id={areaId}
        rows={rows}
        aria-invalid={Boolean(error)}
        className={clsx(
          "w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2",
          error ? "border-rose-400 focus:ring-rose-100" : "border-slate-300 focus:border-brand-500 focus:ring-brand-100",
          className,
        )}
        {...rest}
      />
      {error && <p role="alert" className="mt-1 text-xs font-medium text-rose-600">{error}</p>}
      {!error && hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
});

export default Textarea;
