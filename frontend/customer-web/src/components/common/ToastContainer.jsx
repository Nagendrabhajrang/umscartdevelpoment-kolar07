import { useNotification } from "../../context/NotificationContext";

const TONES = {
  success: "border-brand-200 bg-white text-brand-900",
  error: "border-rose-200 bg-white text-rose-900",
  info: "border-slate-200 bg-white text-slate-900",
};

const ICONS = {
  success: (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="m5 13 4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  error: (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
    </svg>
  ),
  info: (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M12 8h.01M12 12v4" strokeLinecap="round" />
    </svg>
  ),
};

/** Fixed toast stack, bottom on mobile and top-right on desktop. */
export default function ToastContainer() {
  const { toasts, dismiss } = useNotification();
  if (!toasts.length) return null;

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:right-4 sm:top-4 sm:bottom-auto sm:items-end"
      role="region"
      aria-label="Notifications"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          aria-live="polite"
          className={`pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-xl border px-4 py-3 shadow-lg ${
            TONES[t.type] || TONES.info
          }`}
          style={{ animation: "toast-in .22s cubic-bezier(.16,1,.3,1)" }}
        >
          <span className="mt-0.5 shrink-0">{ICONS[t.type] || ICONS.info}</span>
          <p className="flex-1 text-sm font-medium">{t.message}</p>
          <button
            type="button"
            onClick={() => dismiss(t.id)}
            aria-label="Dismiss"
            className="shrink-0 text-slate-400 hover:text-slate-600"
          >
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      ))}
      <style>{`@keyframes toast-in { from { opacity: 0; transform: translateY(-8px) } to { opacity: 1; transform: none } }`}</style>
    </div>
  );
}
