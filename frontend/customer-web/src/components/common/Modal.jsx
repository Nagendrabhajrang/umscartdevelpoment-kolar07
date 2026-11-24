import { useEffect, useRef } from "react";

/**
 * Accessible dialog: Escape closes, focus moves in, background scroll locks.
 * No animation library — a CSS transition on the panel is enough.
 */
export default function Modal({ open, onClose, title, children, footer, size = "md" }) {
  const panelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  const widths = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-2xl" };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <button
        type="button"
        aria-label="Close dialog"
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/50"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`relative w-full ${widths[size]} rounded-t-2xl bg-white shadow-xl outline-none sm:rounded-2xl`}
      >
        {title ? (
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <h2 className="text-base font-bold text-slate-900">{title}</h2>
            {/*
             * No onClose means the dialog is deliberately unclosable (the UPI
             * reference gate). Rendering a dead X in that case invites the
             * customer to click it and conclude the app is broken, so the button
             * only exists when closing is actually possible.
             */}
            {onClose ? (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
                </svg>
              </button>
            ) : null}
          </div>
        ) : null}
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer ? (
          <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-3">{footer}</div>
        ) : null}
      </div>
    </div>
  );
}
