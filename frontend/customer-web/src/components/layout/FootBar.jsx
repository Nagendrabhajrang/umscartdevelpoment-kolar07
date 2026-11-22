import { Link } from "react-router-dom";
import Logo from "../common/Logo";
import { useStore } from "../../context/StoreContext";

/** Site footer: contact details straight from store settings, plus links. */
export default function FootBar() {
  const { settings } = useStore();
  const year = new Date().getFullYear();

  const features = [
    { title: "45-minute delivery", text: "From our local store to your door" },
    { title: "Freshness guaranteed", text: "Or we refund the item, no questions" },
    { title: "Secure checkout", text: "Cash on delivery" },
  ];

  return (
    <footer className="mt-12 border-t border-slate-200 bg-white">
      <div className="container-page py-8">
        <div className="grid gap-2.5 sm:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="rounded-xl bg-slate-50 px-4 py-3">
              <p className="text-sm font-bold text-slate-900">{f.title}</p>
              <p className="mt-0.5 text-xs text-slate-600">{f.text}</p>
            </div>
          ))}
        </div>

        <div className="mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Logo />
            <p className="mt-3 max-w-xs text-sm text-slate-600">
              {settings?.tagline || "Everyday groceries, delivered fast."}
            </p>
          </div>

          <div>
            <h2 className="text-xs font-bold uppercase tracking-wide text-slate-500">Shop</h2>
            <ul className="mt-2.5 space-y-1.5 text-sm">
              {[
                ["/products", "All products"],
                ["/categories", "Categories"],
                ["/cart", "Cart"],
                ["/orders", "Track order"],
              ].map(([to, label]) => (
                <li key={to}>
                  <Link to={to} className="text-slate-600 hover:text-brand-700">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h2 className="text-xs font-bold uppercase tracking-wide text-slate-500">Orders</h2>
            <ul className="mt-2.5 space-y-1.5 text-sm">
              {[
                // Round 27: the public lookup still works for guests who ordered
                // before this release (no account, just an order number).
                ["/track", "Track an order"],
                ["/cart", "Your cart"],
                ["/help", "Help & contact"],
                ["/products", "Shop all"],
              ].map(([to, label]) => (
                <li key={to}>
                  <Link to={to} className="text-slate-600 hover:text-brand-700">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h2 className="text-xs font-bold uppercase tracking-wide text-slate-500">Contact</h2>
            <ul className="mt-2.5 space-y-1.5 text-sm text-slate-600">
              {settings?.contact_phone ? (
                <li>
                  <a href={`tel:${settings.contact_phone}`} className="hover:text-brand-700">
                    {settings.contact_phone}
                  </a>
                </li>
              ) : null}
              {settings?.contact_email ? (
                <li>
                  <a href={`mailto:${settings.contact_email}`} className="hover:text-brand-700">
                    {settings.contact_email}
                  </a>
                </li>
              ) : null}
              {settings?.address ? <li className="text-xs leading-relaxed">{settings.address}</li> : null}
            </ul>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-2 border-t border-slate-200 pt-5 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {year} {settings?.store_name || "UMS Mart"}. Demo store — no real orders are fulfilled.
          </p>
          <p>Prices in {settings?.currency_code || "INR"} · Cash on delivery only</p>
        </div>
      </div>
    </footer>
  );
}
