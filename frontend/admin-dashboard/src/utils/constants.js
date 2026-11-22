/** Shared display constants. Nothing here mirrors business rules - those live
 *  in the backend. This is labels, colours and ordering for the UI only. */

export const ORDER_STATUS_LABELS = {
  pending: "Pending",
  confirmed: "Confirmed",
  processing: "Processing",
  packed: "Packed",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  cancelled: "Cancelled",
  returned: "Returned",
  refunded: "Refunded",
};

export const ORDER_STATUS_STYLES = {
  pending: "bg-amber-100 text-amber-800",
  confirmed: "bg-sky-100 text-sky-800",
  processing: "bg-indigo-100 text-indigo-800",
  packed: "bg-violet-100 text-violet-800",
  out_for_delivery: "bg-blue-100 text-blue-800",
  delivered: "bg-emerald-100 text-emerald-800",
  cancelled: "bg-rose-100 text-rose-800",
  returned: "bg-orange-100 text-orange-800",
  refunded: "bg-slate-100 text-slate-700",
};

export const PAYMENT_STATUS_STYLES = {
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  paid: "bg-emerald-100 text-emerald-800",
  rejected: "bg-rose-100 text-rose-800",
  awaiting_verification: "bg-sky-100 text-sky-800",
  verified: "bg-emerald-100 text-emerald-800",
  collected: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
  // Refunded gets its own colour so it stands out from a plain settled row.
  refunded: "bg-violet-100 text-violet-800",
  cancelled: "bg-slate-100 text-slate-600",
};

export const ADDRESS_LABELS = [
  { value: "home", label: "Home" },
  { value: "work", label: "Work" },
  { value: "other", label: "Other" },
];

export const TICKET_CATEGORIES = [
  { value: "order_issue", label: "Order issue" },
  { value: "payment_issue", label: "Payment issue" },
  { value: "delivery_issue", label: "Delivery issue" },
  { value: "product_quality", label: "Product quality" },
  { value: "wrong_item", label: "Wrong item" },
  { value: "refund_request", label: "Refund request" },
  { value: "account", label: "Account" },
  { value: "other", label: "Other" },
];

export const SORT_OPTIONS = [
  { value: "-created_at", label: "Newest first" },
  { value: "selling_price", label: "Price: low to high" },
  { value: "-selling_price", label: "Price: high to low" },
  { value: "name", label: "Name: A to Z" },
  { value: "-discount_percent", label: "Biggest discount" },
];

export const PAGE_SIZE = 20;


/** Admin-only option lists. */
/** Values copied verbatim from the API enums - do not invent new ones. */
export const PRODUCT_STATUSES = [
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
  { value: "discontinued", label: "Discontinued" },
];

/** UnitTypeEnum: piece, gram, kg, ml, litre, pack, dozen, bunch */
export const UNIT_TYPES = [
  { value: "piece", label: "Piece" },
  { value: "gram", label: "Gram" },
  { value: "kg", label: "Kilogram" },
  { value: "ml", label: "Millilitre" },
  { value: "litre", label: "Litre" },
  { value: "pack", label: "Pack" },
  { value: "dozen", label: "Dozen" },
  { value: "bunch", label: "Bunch" },
];

export const CUSTOMER_STATUSES = [
  { value: "active", label: "Active" },
  { value: "blocked", label: "Blocked" },
  { value: "inactive", label: "Inactive" },
];

export const ORDER_STATUS_FLOW = [
  "pending", "confirmed", "processing", "packed",
  "out_for_delivery", "delivered", "cancelled",
];

export const TICKET_STATUSES = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "awaiting_customer", label: "Awaiting customer" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
];

export const TICKET_PRIORITIES = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
];

/** DiscountTypeEnum: percentage, fixed_amount, free_delivery */
export const DISCOUNT_TYPES = [
  { value: "percentage", label: "Percentage" },
  { value: "fixed_amount", label: "Fixed amount" },
  { value: "free_delivery", label: "Free delivery" },
];

/** BannerPlacementEnum: hero, strip, category, cart, checkout, popup, app */
export const BANNER_PLACEMENTS = [
  { value: "hero", label: "Home hero" },
  { value: "strip", label: "Home strip" },
  { value: "category", label: "Category page" },
  { value: "cart", label: "Cart page" },
  { value: "checkout", label: "Checkout page" },
  { value: "popup", label: "Popup" },
  { value: "app", label: "App banner" },
];

export const LINK_TYPES = [
  { value: "none", label: "No link" },
  { value: "url", label: "External URL" },
  { value: "product", label: "Product" },
  { value: "category", label: "Category" },
  { value: "coupon", label: "Coupon" },
];

/** StockMovementTypeEnum (note: no "expiry" value exists). */
export const MOVEMENT_TYPES = [
  { value: "purchase", label: "Purchase / restock" },
  { value: "adjustment", label: "Manual adjustment" },
  { value: "return", label: "Customer return" },
  { value: "damage", label: "Damage / wastage" },
  { value: "initial", label: "Initial stock" },
];

export const PAYMENT_STATUSES = [
  { value: "pending", label: "Pending" },
  { value: "paid", label: "Paid" },
  { value: "refunded", label: "Refunded" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "verified", label: "Verified" },
  { value: "collected", label: "COD collected" },
  { value: "awaiting_verification", label: "Awaiting verification" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];
