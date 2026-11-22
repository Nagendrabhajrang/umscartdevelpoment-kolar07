import { AlertTriangle, RefreshCw } from "lucide-react";
import Button from "./Button";

export default function ErrorState({ error, onRetry, title = "Could not load data", compact = false }) {
  return (
    <div role="alert" className={`flex flex-col items-center justify-center rounded-xl border border-rose-200 bg-rose-50 text-center ${compact ? "px-4 py-8" : "px-6 py-14"}`}>
      <span className="mb-2 grid h-11 w-11 place-items-center rounded-full bg-rose-100 text-rose-600">
        <AlertTriangle className="h-5 w-5" aria-hidden="true" />
      </span>
      <h3 className="text-sm font-bold text-slate-900">{title}</h3>
      <p className="mt-1 max-w-md text-xs text-slate-600">{error?.message || "Unexpected error."}</p>
      {error?.code === "network_error" && (
        <p className="mt-2 text-xs text-slate-500">
          Is the Django server running on <code className="rounded bg-white px-1">127.0.0.1:8000</code>?
        </p>
      )}
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-3" onClick={onRetry} leftIcon={<RefreshCw className="h-3.5 w-3.5" />}>
          Retry
        </Button>
      )}
    </div>
  );
}
