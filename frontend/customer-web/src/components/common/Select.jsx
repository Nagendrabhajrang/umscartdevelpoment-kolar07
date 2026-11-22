/** Native select — keyboard and mobile behaviour for free. */
export default function Select({ label, error, className = "", id, options = [], placeholder, ...rest }) {
  const selectId = id || rest.name || "select";
  return (
    <div className={className}>
      {label ? (
        <label htmlFor={selectId} className="mb-1.5 block text-xs font-semibold text-slate-700">
          {label}
        </label>
      ) : null}
      <select
        id={selectId}
        className={`h-11 w-full appearance-none rounded-xl border bg-white bg-[length:16px] bg-[right_0.75rem_center] bg-no-repeat px-3 pr-9 text-sm text-slate-900
          focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20
          ${error ? "border-rose-400" : "border-slate-300"}`}
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")",
        }}
        {...rest}
      >
        {placeholder ? <option value="">{placeholder}</option> : null}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error ? <p className="mt-1 text-xs font-medium text-rose-600">{error}</p> : null}
    </div>
  );
}
