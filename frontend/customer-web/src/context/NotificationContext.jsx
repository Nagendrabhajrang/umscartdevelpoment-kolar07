import { createContext, useCallback, useContext, useMemo, useState } from "react";

/**
 * Toast queue. Deliberately tiny: `notify.success/error/info` and a `toasts`
 * array that <ToastContainer> renders. Each toast removes itself.
 */
const NotificationContext = createContext(null);

let nextId = 1;

export function NotificationProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (type, message, timeout = 3800) => {
      if (!message) return null;
      const id = nextId++;
      setToasts((list) => [...list, { id, type, message }]);
      window.setTimeout(() => dismiss(id), timeout);
      return id;
    },
    [dismiss],
  );

  const notify = useMemo(
    () => ({
      success: (m) => push("success", m),
      error: (m) => push("error", m, 5200),
      info: (m) => push("info", m),
    }),
    [push],
  );

  const value = useMemo(
    () => ({ toasts, notify, dismiss }),
    [toasts, notify, dismiss],
  );

  return (
    <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>
  );
}

export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotification must be used inside <NotificationProvider>");
  return ctx;
}

export default NotificationContext;
