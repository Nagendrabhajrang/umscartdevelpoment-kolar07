import { ORDER_STATUS_LABELS, ORDER_STATUS_STYLES, PAYMENT_STATUS_LABELS, PAYMENT_STATUS_STYLES } from "../../utils/constants";

/** Small status pill. Falls back to a neutral style for unknown values. */
export function Badge({ children, className = "", tone }) {
  const TONES = {
    neutral: "bg-slate-100 text-slate-700 ring-slate-200",
    success: "bg-brand-50 text-brand-800 ring-brand-200",
    warning: "bg-amber-50 text-amber-800 ring-amber-200",
    danger: "bg-rose-50 text-rose-800 ring-rose-200",
    info: "bg-sky-50 text-sky-800 ring-sky-200",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${
        TONES[tone] || TONES.neutral
      } ${className}`}
    >
      {children}
    </span>
  );
}

export function OrderStatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${
        ORDER_STATUS_STYLES[status] || "bg-slate-100 text-slate-700 ring-slate-200"
      }`}
    >
      {ORDER_STATUS_LABELS[status] || status}
    </span>
  );
}

export function PaymentStatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${
        PAYMENT_STATUS_STYLES[status] || "bg-slate-100 text-slate-700 ring-slate-200"
      }`}
    >
      {PAYMENT_STATUS_LABELS[status] || status}
    </span>
  );
}

export default Badge;
