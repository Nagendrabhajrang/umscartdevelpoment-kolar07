import clsx from "clsx";

export default function Skeleton({ className = "", rounded = "rounded-md" }) {
  return <div aria-hidden="true" className={clsx("animate-pulse bg-slate-200 motion-reduce:animate-none", rounded, className)} />;
}

export function TableSkeleton({ rows = 6, cols = 5 }) {
  return (
    <div className="space-y-2" aria-busy="true">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-3 rounded-lg border border-slate-100 bg-white p-3">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className={clsx("h-4", c === 0 ? "w-1/4" : "flex-1")} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function StatSkeleton({ count = 4 }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border border-slate-200 bg-white p-4">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-3 h-7 w-20" />
          <Skeleton className="mt-2 h-3 w-16" />
        </div>
      ))}
    </div>
  );
}
