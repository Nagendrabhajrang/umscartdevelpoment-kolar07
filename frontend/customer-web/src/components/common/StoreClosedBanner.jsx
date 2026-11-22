import { useStore } from "../../context/StoreContext";

/** Shown only when the API reports the store is closed for orders. */
export default function StoreClosedBanner() {
  const { settings } = useStore();
  if (!settings || settings.is_store_open !== false) return null;

  return (
    <div className="bg-amber-500 px-4 py-2 text-center text-sm font-semibold text-amber-950">
      {settings.maintenance_message || "The store is closed right now. You can browse, but orders are paused."}
    </div>
  );
}
