/** Shared formatting helpers for the dashboard. Amounts arrive as strings. */

export function formatMoney(value, symbol = "₹") {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return `${symbol}0`;
  return `${symbol}${new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: Number.isInteger(n) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(n)}`;
}

export function compactMoney(value) {
  const n = Number(value ?? 0);
  if (Math.abs(n) >= 10000000) return `₹${(n / 10000000).toFixed(2)} Cr`;
  if (Math.abs(n) >= 100000) return `₹${(n / 100000).toFixed(2)} L`;
  if (Math.abs(n) >= 1000) return `₹${(n / 1000).toFixed(1)}K`;
  return formatMoney(n);
}

export function formatNumber(value) {
  return new Intl.NumberFormat("en-IN").format(Number(value ?? 0));
}

export function formatDate(value, opts) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", opts || { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDateTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function timeAgo(value) {
  if (!value) return "";
  const diff = Date.now() - new Date(value).getTime();
  if (Number.isNaN(diff)) return "";
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(value);
}

export const titleCase = (s = "") =>
  String(s ?? "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export function initials(name = "") {
  return String(name).trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("") || "?";
}

/** Convert an ISO date to the value a <input type="date"> expects. */
export function toDateInput(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString().slice(0, 10);
}

/** Today's date for the date input default. */
export const today = () => new Date().toISOString().slice(0, 10);

/** Build a CSV string from an array of objects and trigger a download. */
export function downloadCsv(filename, rows, columns) {
  if (!rows?.length) return;
  const cols = columns || Object.keys(rows[0]);
  const escape = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [cols.join(","), ...rows.map((r) => cols.map((c) => escape(r[c])).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
