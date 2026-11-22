import clsx from "clsx";
import { ArrowDown, ArrowUp } from "lucide-react";
import { TableSkeleton } from "../common/Skeleton";
import EmptyState from "../common/EmptyState";

/**
 * Generic, accessible data table.
 *
 * columns: [{ key, header, render?(row), sortable?, className?, align? }]
 * Sorting is server-side: pass `sort` + `onSortChange` and the parent adds
 * `ordering` to the query. Rows without a `render` print `row[key]`.
 */
export default function DataTable({
  columns = [], rows = [], loading = false, error = null,
  emptyTitle = "Nothing here yet", emptyDescription, emptyAction,
  sort, onSortChange, rowKey = "id", onRowClick, caption,
}) {
  if (loading) return <TableSkeleton cols={columns.length} />;

  if (error) {
    return (
      <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
        {error.message || "Could not load this table."}
      </div>
    );
  }

  if (!rows.length) {
    return <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} compact />;
  }

  const sortKey = sort?.replace(/^-/, "");
  const sortDesc = sort?.startsWith("-");

  const header = (col) => {
    const isSorted = sortKey === col.key;
    const content = (
      <span className="inline-flex items-center gap-1">
        {col.header}
        {isSorted && (sortDesc ? <ArrowDown className="h-3 w-3" aria-hidden="true" /> : <ArrowUp className="h-3 w-3" aria-hidden="true" />)}
      </span>
    );
    if (!col.sortable || !onSortChange) return content;
    return (
      <button
        type="button"
        onClick={() => onSortChange(isSorted && !sortDesc ? `-${col.key}` : isSorted && sortDesc ? col.key : col.key)}
        className="inline-flex items-center gap-1 rounded font-semibold hover:text-brand-700"
        aria-label={`Sort by ${col.header}`}
      >
        {content}
      </button>
    );
  };

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      {/* `relative` is load-bearing: a statically-positioned overflow container
          still reports its content's width as document overflow in Chrome, so
          the 720px-wide table scrolled the whole PAGE on phones instead of
          scrolling inside this box. */}
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={clsx(
                    "whitespace-nowrap px-3 py-2.5 text-[11px] font-bold uppercase tracking-wide text-slate-500",
                    col.align === "right" && "text-right",
                    col.align === "center" && "text-center",
                    col.className,
                  )}
                >
                  {header(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => (
              <tr
                key={row[rowKey]}
                className={clsx("transition", onRowClick && "cursor-pointer hover:bg-slate-50")}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={clsx(
                      "px-3 py-2.5 align-middle text-slate-700",
                      col.align === "right" && "text-right tabular-nums",
                      col.align === "center" && "text-center",
                      col.className,
                    )}
                  >
                    {col.render ? col.render(row) : row[col.key] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
