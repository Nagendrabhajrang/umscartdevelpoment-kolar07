import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

/** Toast queue for the dashboard. One provider, used by every page. */
const NotificationContext = createContext(null);
let seq = 0;

export function NotificationProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id));
    const t = timers.current.get(id);
    if (t) { clearTimeout(t); timers.current.delete(id); }
  }, []);

  const push = useCallback((message, variant = "info", options = {}) => {
    if (!message) return null;
    const id = ++seq;
    const toast = { id, message, variant, title: options.title || null, duration: options.duration ?? 3800 };
    setToasts((list) => [...list.slice(-3), toast]);
    if (toast.duration > 0) timers.current.set(id, setTimeout(() => dismiss(id), toast.duration));
    return id;
  }, [dismiss]);

  const notify = useMemo(() => ({
    success: (m, o) => push(m, "success", o),
    error: (m, o) => push(m, "error", { duration: 5200, ...o }),
    info: (m, o) => push(m, "info", o),
    warning: (m, o) => push(m, "warning", o),
    dismiss,
  }), [push, dismiss]);

  const value = useMemo(() => ({ toasts, notify, dismiss }), [toasts, notify, dismiss]);
  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotification must be used inside <NotificationProvider>");
  return ctx;
}

export default NotificationContext;
