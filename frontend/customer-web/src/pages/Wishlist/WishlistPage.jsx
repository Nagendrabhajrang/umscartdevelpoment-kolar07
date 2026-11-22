import { Link, useNavigate } from "react-router-dom";
import { useWishlist } from "../../context/WishlistContext";
import { useCart } from "../../context/CartContext";
import { wishlistService } from "../../services/wishlistService";
import { useNotification } from "../../context/NotificationContext";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import Button from "../../components/common/Button";
import Skeleton from "../../components/common/Skeleton";
import { formatMoney } from "../../utils/format";

/** Saved products with move-to-cart and remove. */
export default function WishlistPage() {
  const { items, loading, refresh, remove } = useWishlist();
  const { refresh: refreshCart } = useCart();
  const { notify } = useNotification();
  const navigate = useNavigate();

  const moveToCart = async (item) => {
    try {
      await wishlistService.moveToCart(item.id, 1);
      await refreshCart();
      await refresh();
      notify.success("Moved to cart");
      navigate("/cart");
    } catch (e) {
      notify.error(e?.message || "Could not move that item");
    }
  };

  return (
    <div className="container-page py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Wishlist</h1>
        <p className="mt-1 text-sm text-slate-600">Things you saved for later.</p>
      </header>

      {loading ? (
        <div className="space-y-2.5">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-2xl" />
          ))}
        </div>
      ) : !items.length ? (
        <EmptyState
          icon={
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8Z" strokeLinejoin="round" />
            </svg>
          }
          title="Nothing saved yet"
          description="Tap the heart on any product to keep it here."
          action={<Button as={Link} to="/products" size="lg">Browse products</Button>}
        />
      ) : (
        <ul className="space-y-2.5">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3">
              <div className="h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-slate-50">
                {(item.product_image_url || item.product_image) ? (
                  <img src={item.product_image_url || item.product_image} alt="" className="h-full w-full object-contain" />
                ) : null}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-900">
                  {item.product_name || `Product #${item.product}`}
                </p>
                <p className="text-[11px] text-slate-500">{item.unit_label}</p>
                {item.selling_price ? (
                  <p className="mt-0.5 text-sm font-bold text-slate-900">{formatMoney(item.selling_price)}</p>
                ) : null}
              </div>
              <div className="flex shrink-0 gap-2">
                <Button size="sm" onClick={() => moveToCart(item)}>Move to cart</Button>
                <Button size="sm" variant="secondary" onClick={() => remove(item.id)}>Remove</Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
