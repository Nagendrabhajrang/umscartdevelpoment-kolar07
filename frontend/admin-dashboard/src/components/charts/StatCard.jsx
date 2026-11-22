import clsx from "clsx";
import { TrendingDown, TrendingUp } from "lucide-react";
import SparkLine from "./SparkLine";

/**
 * KPI tile. `value` is always supplied by the caller from an API response -
 * there are no default numbers anywhere in this dashboard.
 */
export default function StatCard({ label, value, sublabel, icon: Icon, tone = "brand", trend, trendLabel, spark }) {
  const tones = {
    brand: "bg-brand-50 text-brand-700",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    rose: "bg-rose-50 text-rose-700",
    sky: "bg-sky-50 text-sky-700",
    violet: "bg-violet-50 text-violet-700",
  };

  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-3 shadow-card sm:p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[11px] font-semibold uppercase tracking-wide text-slate-500 sm:text-xs">{label}</p>
          {/* Currency values like ₹2,810.73 are wider than a half-width column
              on a 280px phone, so they step down instead of pushing the page. */}
          <p className="mt-1.5 break-words text-lg font-extrabold tracking-tight text-slate-900 sm:text-2xl">{value}</p>
          {sublabel && <p className="mt-0.5 truncate text-xs text-slate-500">{sublabel}</p>}
        </div>
        {Icon && (
          <span className={clsx("grid h-9 w-9 shrink-0 place-items-center rounded-lg", tones[tone])}>
            <Icon className="h-4.5 w-4.5" aria-hidden="true" />
          </span>
        )}
      </div>

      {(trend !== undefined || spark) && (
        <div className="mt-2.5 flex items-end justify-between gap-2">
          {trend !== undefined && (
            <span className={clsx("inline-flex items-center gap-1 text-xs font-semibold", trend >= 0 ? "text-emerald-600" : "text-rose-600")}>
              {trend >= 0 ? <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" /> : <TrendingDown className="h-3.5 w-3.5" aria-hidden="true" />}
              {Math.abs(trend).toFixed(1)}%
              {trendLabel && <span className="font-normal text-slate-400">{trendLabel}</span>}
            </span>
          )}
          {spark && <SparkLine values={spark} />}
        </div>
      )}
    </div>
  );
}
