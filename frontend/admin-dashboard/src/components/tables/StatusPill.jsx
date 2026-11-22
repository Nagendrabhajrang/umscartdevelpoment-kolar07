import clsx from "clsx";
import { Check, X } from "lucide-react";

/** Inline toggle used in table cells (active / inactive, on / off). */
export default function StatusPill({ active, activeLabel = "Active", inactiveLabel = "Inactive", onClick, busy = false }) {
  const Tag = onClick ? "button" : "span";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      onClick={onClick}
      disabled={onClick ? busy : undefined}
      aria-pressed={onClick ? active : undefined}
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold",
        active ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600",
        onClick && "transition hover:opacity-80 disabled:opacity-50",
      )}
    >
      {active ? <Check className="h-2.5 w-2.5" aria-hidden="true" /> : <X className="h-2.5 w-2.5" aria-hidden="true" />}
      {active ? activeLabel : inactiveLabel}
    </Tag>
  );
}
