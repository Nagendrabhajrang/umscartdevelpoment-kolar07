import { CheckCircle2, Info, AlertTriangle, XCircle, X } from "lucide-react";
import { useNotification } from "../../context/NotificationContext";

const ICONS = { success: CheckCircle2, error: XCircle, warning: AlertTriangle, info: Info };
const TONES = {
  success: "border-emerald-200 text-emerald-700",
  error: "border-rose-200 text-rose-700",
  warning: "border-amber-200 text-amber-700",
  info: "border-sky-200 text-sky-700",
};

export default function ToastContainer() {
  const { toasts, dismiss } = useNotification();
  return (
    <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2">
      {toasts.map((toast) => {
        const Icon = ICONS[toast.variant] || Info;
        return (
          <div
            key={toast.id}
            role={toast.variant === "error" ? "alert" : "status"}
            className={`pointer-events-auto flex items-start gap-2.5 rounded-lg border bg-white px-3.5 py-2.5 shadow-lg ${TONES[toast.variant] || TONES.info}`}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p className="flex-1 text-sm font-medium text-slate-700">{toast.message}</p>
            <button type="button" onClick={() => dismiss(toast.id)} aria-label="Dismiss"
              className="rounded p-0.5 text-slate-400 hover:text-slate-700">
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
