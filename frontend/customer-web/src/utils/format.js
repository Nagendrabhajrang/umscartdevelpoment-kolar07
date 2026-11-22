/** Money, dates and text helpers. Kept free of React so any layer can use them. */

const SYMBOL = "₹";

export function formatMoney(value, symbol = SYMBOL) {
  const n = Number(value);
  if (!Number.isFinite(n)) return `${symbol}0.00`;
  return `${symbol}${n.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/** Whole rupees when the value has no paise — used for big headline numbers. */
export function formatMoneyShort(value, symbol = SYMBOL) {
  const n = Number(value);
  if (!Number.isFinite(n)) return `${symbol}0`;
  return Number.isInteger(n)
    ? `${symbol}${n.toLocaleString("en-IN")}`
    : formatMoney(n, symbol);
}

export const formatCurrency = formatMoney;

export function formatDate(value, opts) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", opts || { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function relativeTime(value) {
  if (!value) return "—";
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = Math.round((then - Date.now()) / 1000);
  const units = [
    ["year", 31536000],
    ["month", 2592000],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  const fmt = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [unit, secs] of units) {
    if (Math.abs(diff) >= secs) return fmt.format(Math.round(diff / secs), unit);
  }
  return "just now";
}

export const titleCase = (s = "") =>
  String(s)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();

export function initials(name = "") {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("");
}

/** "3 items" / "1 item" */
export function pluralise(n, singular, plural) {
  return `${n} ${n === 1 ? singular : plural || `${singular}s`}`;
}

/** Compact order line: "Aashirvaad Atta +2 more" */
export function summariseItems(items = []) {
  if (!items?.length) return "";
  const first = items[0].product_name || items[0].name || "";
  return items.length === 1 ? first : `${first} +${items.length - 1} more`;
}
