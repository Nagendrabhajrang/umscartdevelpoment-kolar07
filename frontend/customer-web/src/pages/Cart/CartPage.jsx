import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useCart } from "../../context/CartContext";
import { useStore } from "../../context/StoreContext";
import QuantityStepper from "../../components/common/QuantityStepper";
import Button from "../../components/common/Button";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import Skeleton from "../../components/common/Skeleton";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import { formatMoney } from "../../utils/format";

/** Cart page. All money comes from the server — this only renders it. */
export default function CartPage() {
  const { cart, items, loading, error, setQuantity, remove, clear, refresh } = useCart();
  const { isAuthenticated } = useAuth();
  const { settings } = useStore();
  const navigate = useNavigate();
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing] = useState(false);

  if (loading && !cart) {
    return (
      <div className="container-page py-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Your cart</h1>
        <div className="mt-4 space-y-2.5">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error && !cart) {
    return (
      <div className="container-page py-8">
        <ErrorState error={error} onRetry={refresh} title="Your cart could not be loaded" />
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="container-page py-8">
        <EmptyState
          icon={
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="9" cy="20" r="1.5" />
              <circle cx="18" cy="20" r="1.5" />
              <path d="M2 3h2.2l2.3 12h11.2l2.3-8H6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          }
          title="Your cart is empty"
          description="Add a few things and they will show up here."
          action={<Button as={Link} to="/products" size="lg">Browse products</Button>}
        />
      </div>
    );
  }

  const itemCount = cart?.item_count ?? items.length;

  return (
    <div className="container-page py-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          Your cart <span className="text-base font-semibold text-slate-500">({itemCount} item{itemCount === 1 ? "" : "s"})</span>
        </h1>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={refresh}>Refresh</Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirmClear(true)}>Clear cart</Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        {/* Items */}
        <ul className="space-y-2.5">
          {items.map((item) => (
            <li key={item.id} className="flex gap-3 rounded-2xl border border-slate-200 bg-white p-3">
              <Link to={`/product/${item.product}`} className="shrink-0">
                <div className="h-20 w-20 overflow-hidden rounded-xl bg-slate-50">
                  {(item.product_image_url || item.product_image) ? (
                    <img src={item.product_image_url || item.product_image} alt={item.product_name} className="h-full w-full object-contain" />
                  ) : null}
                </div>
              </Link>

              <div className="flex min-w-0 flex-1 flex-col">
                <Link
                  to={`/product/${item.product}`}
                  className="line-clamp-2 text-sm font-semibold text-slate-900 hover:text-brand-700"
                >
                  {item.product_name}
                </Link>
                <p className="mt-0.5 text-[11px] text-slate-500">{item.unit_label}</p>

                {!item.is_available ? (
                  <p className="mt-1 text-[11px] font-bold text-rose-600">No longer available</p>
                ) : null}

                <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-2">
                  <QuantityStepper
                    value={item.quantity}
                    onChange={(v) => setQuantity(item.id, v)}
                    min={1}
                    max={Math.max(1, Math.min(item.available_quantity ?? 99, 99))}
                    size="sm"
                  />
                  <div className="text-right">
                    <p className="text-sm font-extrabold text-slate-900">{formatMoney(item.line_total)}</p>
                    {Number(item.line_savings) > 0 ? (
                      <p className="text-[11px] font-semibold text-brand-700">
                        Saved {formatMoney(item.line_savings)}
                      </p>
                    ) : null}
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => remove(item.id)}
                aria-label={`Remove ${item.product_name}`}
                className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center self-start rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600"
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
                </svg>
              </button>
            </li>
          ))}
        </ul>

        {/* Bill */}
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-bold text-slate-900">Order summary</h2>
            <dl className="mt-3 space-y-2 text-sm">
              <Row label={`Subtotal (MRP)`} value={formatMoney(cart.mrp_total)} muted />
              <Row label="Product savings" value={`− ${formatMoney(cart.savings)}`} positive />
              <Row label="Subtotal" value={formatMoney(cart.subtotal)} />
              <div className="h-px bg-slate-100" />
              <Row label="To pay" value={formatMoney(cart.subtotal)} bold />
            </dl>

            <FreeDeliveryBar
              subtotal={Number(cart.subtotal)}
              threshold={Number(settings?.free_delivery_threshold ?? 499)}
            />

            <p className="mt-2 text-[11px] text-slate-500">
              Delivery, packaging and taxes are calculated at checkout.
            </p>

            <Button
              size="lg"
              fullWidth
              className="mt-4"
              onClick={() =>
                isAuthenticated
                  ? navigate("/checkout")
                  : // Round 27: the checkout gate sends them to login anyway, but
                    // navigating here directly lets us pass the basket size so the
                    // login screen can reassure them nothing is lost.
                    navigate("/login", {
                      state: {
                        from: { pathname: "/checkout" },
                        reason: "checkout",
                        cartCount: cart?.item_count ?? 0,
                      },
                    })
              }
              disabled={settings?.is_store_open === false}
            >
              {settings?.is_store_open === false ? "Store is closed" : "Proceed to checkout"}
            </Button>

            <p className="mt-2 text-center text-[11px] font-medium text-slate-500">
              {isAuthenticated
                ? "You pay cash when the order arrives."
                : "You'll sign in with your mobile number — no password needed."}
            </p>

            <Link to="/products" className="mt-3 block text-center text-sm font-semibold text-brand-700 hover:underline">
              Continue shopping
            </Link>
          </div>

          <div className="mt-3 rounded-2xl border border-dashed border-brand-300 bg-brand-50/60 p-3.5">
            <p className="text-xs font-bold text-brand-900">Cash on delivery</p>
            <p className="mt-0.5 text-[11px] leading-relaxed text-brand-800/80">
              Pay the delivery partner when your order arrives. Keep exact change handy.
            </p>
          </div>
        </aside>
      </div>

      <ConfirmDialog
        open={confirmClear}
        title="Clear your cart?"
        description="Every item will be removed. This cannot be undone."
        confirmLabel="Clear cart"
        loading={clearing}
        onConfirm={async () => {
          setClearing(true);
          await clear();
          setClearing(false);
          setConfirmClear(false);
        }}
        onClose={() => setConfirmClear(false)}
      />
    </div>
  );
}

/**
 * How much more to spend for free delivery. Shows nothing when the threshold is
 * unknown or already met, so it never nags a customer who already qualifies.
 */
function FreeDeliveryBar({ subtotal, threshold }) {
  if (!threshold || Number.isNaN(threshold)) return null;
  const remaining = threshold - subtotal;
  if (subtotal <= 0) return null;

  if (remaining <= 0) {
    return (
      <div className="mt-3 rounded-lg bg-brand-50 px-2.5 py-2 text-[11px] font-semibold text-brand-800">
        Free delivery unlocked
      </div>
    );
  }

  const pct = Math.min(100, Math.round((subtotal / threshold) * 100));
  return (
    <div className="mt-3">
      <p className="text-[11px] font-semibold text-slate-600">
        Add <span className="text-brand-700">{formatMoney(remaining)}</span> more for free delivery
      </p>
      <div
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Progress towards free delivery"
      >
        <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Row({ label, value, muted, positive, bold }) {
  return (
    <div className="flex items-center justify-between">
      <dt className={`${muted ? "text-slate-500" : "text-slate-600"} ${bold ? "font-bold text-slate-900" : ""}`}>
        {label}
      </dt>
      <dd
        className={`tabular-nums ${
          positive ? "font-semibold text-brand-700" : bold ? "text-base font-extrabold text-slate-900" : "text-slate-800"
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
