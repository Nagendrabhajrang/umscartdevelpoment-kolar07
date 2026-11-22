/** Multi-line input with the same label/error conventions as <Input>. */
export default function Textarea({ label, error, hint, className = "", id, rows = 3, ...rest }) {
  const areaId = id || rest.name || "textarea";
  return (
    <div className={className}>
      {label ? (
        <label htmlFor={areaId} className="mb-1.5 block text-xs font-semibold text-slate-700">
          {label}
        </label>
      ) : null}
      <textarea
        id={areaId}
        rows={rows}
        className={`w-full rounded-xl border bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400
          focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20
          ${error ? "border-rose-400" : "border-slate-300"}`}
        aria-invalid={error ? "true" : undefined}
        {...rest}
      />
      {error ? <p className="mt-1 text-xs font-medium text-rose-600">{error}</p> : null}
      {!error && hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}
