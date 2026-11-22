/** Shimmering placeholder. Announce nothing — it is decoration. */
export default function Skeleton({ className = "h-4 w-full" }) {
  return (
    <div
      aria-hidden="true"
      className={`relative overflow-hidden rounded-md bg-slate-200/70 ${className}`}
    >
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/60 to-transparent" />
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="card space-y-3">
      <Skeleton className="h-36 w-full rounded-xl" />
      <Skeleton className="h-3.5 w-3/4" />
      <Skeleton className="h-3 w-1/3" />
      <Skeleton className="h-9 w-full rounded-lg" />
    </div>
  );
}

export function SkeletonRows({ rows = 4 }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full rounded-xl" />
      ))}
    </div>
  );
}
