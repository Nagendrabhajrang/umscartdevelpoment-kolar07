import { useEffect, useState } from "react";

/** Seconds remaining until `target`, ticking once a second. Null target → 0. */
export default function useCountdown(target) {
  const calc = () =>
    target ? Math.max(0, Math.floor((new Date(target).getTime() - Date.now()) / 1000)) : 0;
  const [remaining, setRemaining] = useState(calc);

  useEffect(() => {
    setRemaining(calc());
    if (!target) return undefined;
    const id = setInterval(() => setRemaining(calc()), 1000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");
  return { remaining, label: `${mm}:${ss}` };
}
