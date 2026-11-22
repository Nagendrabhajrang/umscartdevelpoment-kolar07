import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import clsx from "clsx";

/**
 * Dashboard dialog. Handles Escape, focus trapping and scroll locking, and
 * animates with a short CSS transition (respects reduced motion via the base
 * stylesheet).
 */
export default function Modal({ open, onClose, title, description, children, footer, size = "md" }) {
  const panel = useRef(null);
  const lastFocus = useRef(null);
  // Keep the latest onClose without re-running the effect. Re-running it on
  // every parent render stole focus back to the first field mid-typing.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const sizes = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl", full: "max-w-6xl" };

  useEffect(() => {
    if (!open) return undefined;
    lastFocus.current = document.activeElement;
    const onKey = (e) => {
      if (e.key === "Escape") onCloseRef.current?.();
      if (e.key === "Tab" && panel.current) {
        const f = panel.current.querySelectorAll('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])');
        if (!f.length) return;
        const first = f[0]; const last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const t = setTimeout(() => panel.current?.querySelector("input,select,textarea,button")?.focus(), 30);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
      clearTimeout(t);
      lastFocus.current?.focus?.();
    };
    // `open` only: onClose is read through a ref so typing does not steal focus.
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-slate-900/50" onClick={onClose} aria-hidden="true" />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dlg-title"
        className={clsx("relative flex min-h-0 max-h-[92vh] w-full flex-col rounded-t-xl bg-white shadow-xl sm:rounded-xl", sizes[size])}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-3.5">
          <div>
            <h2 id="dlg-title" className="text-base font-bold text-slate-900">{title}</h2>
            {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
          </div>
          <button type="button" onClick={onClose} aria-label="Close dialog"
            className="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700">
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="border-t border-slate-200 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}
