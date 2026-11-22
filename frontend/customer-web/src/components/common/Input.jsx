import { forwardRef } from "react";

/** Labelled text input with inline error text. */
const Input = forwardRef(function Input(
  { label, error, hint, className = "", id, required, icon, ...rest },
  ref,
) {
  const inputId = id || rest.name || "input";
  return (
    <div className={className}>
      {label ? (
        <label htmlFor={inputId} className="mb-1.5 block text-xs font-semibold text-slate-700">
          {label}
          {required ? <span className="ml-0.5 text-rose-600">*</span> : null}
        </label>
      ) : null}
      <div className="relative">
        {icon ? (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
            {icon}
          </span>
        ) : null}
        <input
          ref={ref}
          id={inputId}
          className={`h-11 w-full rounded-xl border bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400
            focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20
            ${icon ? "pl-9" : ""}
            ${error ? "border-rose-400" : "border-slate-300"}`}
          aria-invalid={error ? "true" : undefined}
          {...rest}
        />
      </div>
      {error ? <p className="mt-1 text-xs font-medium text-rose-600">{error}</p> : null}
      {!error && hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
});

export default Input;
