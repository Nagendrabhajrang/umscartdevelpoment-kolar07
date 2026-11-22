/** Labelling and colour maps shared by every page. */

export const ORDER_STATUS_LABELS = {
  pending: "Pending",
  confirmed: "Confirmed",
  processing: "Processing",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

/** Badge classes — neutral, positive, caution, negative. */
export const ORDER_STATUS_STYLES = {
  pending: "bg-amber-50 text-amber-800 ring-amber-200",
  confirmed: "bg-sky-50 text-sky-800 ring-sky-200",
  processing: "bg-indigo-50 text-indigo-800 ring-indigo-200",
  out_for_delivery: "bg-violet-50 text-violet-800 ring-violet-200",
  delivered: "bg-brand-50 text-brand-800 ring-brand-200",
  cancelled: "bg-rose-50 text-rose-800 ring-rose-200",
};

export const PAYMENT_STATUS_LABELS = {
  pending: "Cash due",
  approved: "Approved",
  rejected: "Rejected",
  paid: "Paid",
  cod_due: "Cash due",
  cod_collected: "Cash collected",
  refunded: "Refunded",
  failed: "Failed",
};

export const PAYMENT_STATUS_STYLES = {
  pending: "bg-amber-50 text-amber-800 ring-amber-200",
  approved: "bg-sky-50 text-sky-800 ring-sky-200",
  rejected: "bg-rose-50 text-rose-800 ring-rose-200",
  paid: "bg-brand-50 text-brand-800 ring-brand-200",
  cod_due: "bg-amber-50 text-amber-800 ring-amber-200",
  cod_collected: "bg-brand-50 text-brand-800 ring-brand-200",
  refunded: "bg-slate-100 text-slate-700 ring-slate-200",
  failed: "bg-rose-50 text-rose-800 ring-rose-200",
};

export const CANCELLATION_REASONS = [
  { value: "customer_request", label: "I changed my mind" },
  { value: "ordered_by_mistake", label: "Ordered by mistake" },
  { value: "found_better_price", label: "Found a better price" },
  { value: "delivery_too_slow", label: "Delivery is taking too long" },
  { value: "other", label: "Something else" },
];

export const ADDRESS_LABELS = [
  { value: "home", label: "Home" },
  { value: "work", label: "Work" },
  { value: "other", label: "Other" },
];

/**
 * Only orderings the API actually honours.
 * ProductListCreateView.ordering_fields = created_at, name, selling_price, mrp,
 * display_order — anything else is silently ignored by DRF and falls back to the
 * default (display_order, name), which looks like a broken sort to the user.
 */
export const SORT_OPTIONS = [
  { value: "display_order", label: "Recommended" },
  { value: "-created_at", label: "Newest first" },
  { value: "selling_price", label: "Price: low to high" },
  { value: "-selling_price", label: "Price: high to low" },
  { value: "name", label: "Name A–Z" },
  { value: "-name", label: "Name Z–A" },
];

export const PAGE_SIZE = 20;
