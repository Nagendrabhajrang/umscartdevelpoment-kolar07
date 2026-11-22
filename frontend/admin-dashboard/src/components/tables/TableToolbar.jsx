import { Search, Download, RotateCcw } from "lucide-react";
import Input from "../common/Input";
import Button from "../common/Button";

/** Search + filter slot + export for any table page. */
export default function TableToolbar({
  search, onSearchChange, searchPlaceholder = "Search…",
  filters = null, onExport, onRefresh, refreshing = false, children,
}) {
  return (
    <div className="mb-3 flex flex-wrap items-end gap-2">
      <Input
        aria-label="Search"
        value={search}
        onChange={(e) => onSearchChange?.(e.target.value)}
        placeholder={searchPlaceholder}
        leftIcon={<Search className="h-4 w-4" />}
        containerClassName="w-full sm:w-64"
        className="h-9"
      />
      {filters}
      <div className="ml-auto flex items-center gap-1.5">
        {children}
        {onRefresh && (
          <Button variant="outline" size="sm" onClick={onRefresh} leftIcon={<RotateCcw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />}>
            Refresh
          </Button>
        )}
        {onExport && (
          <Button variant="outline" size="sm" onClick={onExport} leftIcon={<Download className="h-3.5 w-3.5" />}>
            Export CSV
          </Button>
        )}
      </div>
    </div>
  );
}
