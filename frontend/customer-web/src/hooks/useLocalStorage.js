import { useCallback, useState } from "react";

/** localStorage-backed state that degrades to plain state when storage is blocked. */
export default function useLocalStorage(key, initialValue) {
  const read = () => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw === null ? initialValue : JSON.parse(raw);
    } catch {
      return initialValue;
    }
  };

  const [value, setValue] = useState(read);

  const set = useCallback(
    (next) => {
      setValue((prev) => {
        const resolved = typeof next === "function" ? next(prev) : next;
        try {
          window.localStorage.setItem(key, JSON.stringify(resolved));
        } catch {
          /* storage full or disabled — state still updates */
        }
        return resolved;
      });
    },
    [key],
  );

  return [value, set];
}
