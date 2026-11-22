import Select from "../common/Select";
import { SORT_OPTIONS } from "../../utils/constants";

/** Sort + category + in-stock controls for listing pages. */
export default function ProductFilters({ categories = [], value, onChange, count }) {
  const set = (key) => (e) => onChange({ ...value, [key]: e.target.value });

  const categoryOptions = [
    { value: "", label: "All categories" },
    ...categories.map((c) => ({ value: String(c.id), label: c.name })),
  ];

  return (
    <div className="flex flex-wrap items-end gap-2.5">
      <Select
        aria-label="Filter by category"
        options={categoryOptions}
        value={value.category || ""}
        onChange={set("category")}
        className="min-w-44 flex-1 sm:max-w-56"
      />
      <Select
        aria-label="Sort products"
        options={SORT_OPTIONS}
        value={value.ordering || "-created_at"}
        onChange={set("ordering")}
        className="min-w-40 flex-1 sm:max-w-48"
      />
      <label className="inline-flex h-11 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700">
        <input
          type="checkbox"
          checked={Boolean(value.in_stock)}
          onChange={(e) => onChange({ ...value, in_stock: e.target.checked ? "true" : "" })}
          className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
        />
        In stock only
      </label>
      {typeof count === "number" ? (
        <span className="ml-auto self-center text-xs font-semibold text-slate-500">
          {count} product{count === 1 ? "" : "s"}
        </span>
      ) : null}
    </div>
  );
}
