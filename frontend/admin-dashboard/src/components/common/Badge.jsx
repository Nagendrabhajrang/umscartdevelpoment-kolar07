import clsx from "clsx";
import { ORDER_STATUS_LABELS, ORDER_STATUS_STYLES, PAYMENT_STATUS_STYLES } from "../../utils/constants";
import { titleCase } from "../../utils/format";

const TONES = {
  slate: "bg-slate-100 text-slate-700",
  green: "bg-emerald-100 text-emerald-800",
  amber: "bg-amber-100 text-amber-800",
  red: "bg-rose-100 text-rose-800",
  blue: "bg-sky-100 text-sky-800",
  violet: "bg-violet-100 text-violet-800",
  indigo: "bg-indigo-100 text-indigo-800",
};

export default function Badge({ children, tone = "slate", className = "", dot = false }) {
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold", TONES[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />}
      {children}
    </span>
  );
}

export function OrderStatusBadge({ status }) {
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold", ORDER_STATUS_STYLES[status] || "bg-slate-100 text-slate-700")}>
      {ORDER_STATUS_LABELS[status] || titleCase(status)}
    </span>
  );
}

export function PaymentStatusBadge({ status }) {
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold", PAYMENT_STATUS_STYLES[status] || "bg-slate-100 text-slate-700")}>
      {titleCase(status)}
    </span>
  );
}
