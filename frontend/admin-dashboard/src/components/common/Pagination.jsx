import { ChevronLeft, ChevronRight } from "lucide-react";
import Button from "./Button";

export default function Pagination({ count, page, pageSize, onPageChange, hasNext, hasPrevious }) {
  const totalPages = Math.max(1, Math.ceil((count || 0) / (pageSize || 20)));
  if (totalPages <= 1) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(count, page * pageSize);

  return (
    <div className="flex flex-col items-center justify-between gap-2 py-3 sm:flex-row">
      <p className="text-xs text-slate-500">
        Showing <span className="font-semibold text-slate-700">{from}</span>–<span className="font-semibold text-slate-700">{to}</span> of{" "}
        <span className="font-semibold text-slate-700">{count}</span>
      </p>
      <div className="flex items-center gap-1.5">
        <Button variant="outline" size="xs" disabled={!hasPrevious && page <= 1} onClick={() => onPageChange(page - 1)} leftIcon={<ChevronLeft className="h-3.5 w-3.5" />}>
          Prev
        </Button>
        <span className="px-1.5 text-xs font-semibold text-slate-600">{page} / {totalPages}</span>
        <Button variant="outline" size="xs" disabled={!hasNext && page >= totalPages} onClick={() => onPageChange(page + 1)} rightIcon={<ChevronRight className="h-3.5 w-3.5" />}>
          Next
        </Button>
      </div>
    </div>
  );
}
