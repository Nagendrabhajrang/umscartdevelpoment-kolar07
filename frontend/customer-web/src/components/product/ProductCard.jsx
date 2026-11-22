import { Link } from "react-router-dom";
import { useCart } from "../../context/CartContext";
import { formatMoney } from "../../utils/format";

/**
 * The product tile used on every listing surface.
 *
 * The red count chip mirrors Amazon/JioMart: it shows how many of this item are
 * already in the cart and appears only when that number is above zero. It is a
 * plain CSS transition on mount — no animation library, so it can never block
 * rendering.
 */
export default function ProductCard({ product, compact = false }) {
  const { add, busyProduct } = useCart();

  const busy = busyProduct === product.id;
  const outOfStock = product.in_stock === false;
  const discount = Math.round(Number(product.discount_percent) || 0);

  const image = product.primary_image || product.image_url;

  return (
    <div
      className={`group relative flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card transition-shadow hover:shadow-card-hover ${
        compact ? "p-2.5" : "p-3"
      }`}
    >
      <Link to={`/product/${product.id}`} className="block">
        <div className="relative overflow-hidden rounded-xl bg-slate-50">
          {image ? (
            <img
              src={image}
              alt={product.name}
              loading="lazy"
              className={`w-full object-contain transition-transform duration-300 group-hover:scale-[1.03] ${
                compact ? "aspect-square" : "aspect-square"
              } ${outOfStock ? "opacity-45 grayscale" : ""}`}
            />
          ) : (
            <div className="grid aspect-square place-items-center text-slate-300">
              <svg viewBox="0 0 24 24" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="9" cy="9" r="1.5" />
                <path d="m21 15-5-5L5 21" />
              </svg>
            </div>
          )}

          {discount > 0 ? (
            <span className="absolute right-2 top-2 rounded-md bg-brand-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
              {discount}% OFF
            </span>
          ) : null}

          {outOfStock ? (
            <span className="absolute inset-x-0 bottom-0 bg-slate-900/80 py-1 text-center text-[11px] font-bold text-white">
              Out of stock
            </span>
          ) : null}
        </div>
      </Link>

      <div className="mt-2.5 flex flex-1 flex-col">
        <Link
          to={`/product/${product.id}`}
          className="line-clamp-2 min-h-[2.5rem] text-sm font-semibold leading-snug text-slate-900 hover:text-brand-700"
        >
          {product.name}
        </Link>
        <p className="mt-0.5 text-[11px] text-slate-500">{product.unit_label || product.category_name}</p>

        <div className="mt-2 flex items-end gap-1.5">
          <span className="text-base font-extrabold text-slate-900">
            {formatMoney(product.selling_price)}
          </span>
          {Number(product.mrp) > Number(product.selling_price) ? (
            <span className="pb-0.5 text-xs text-slate-400 line-through">
              {formatMoney(product.mrp)}
            </span>
          ) : null}
        </div>

        {/* mt-auto pins the action to the card floor, so every button in a
            row sits on the same line no matter how long the product name is. */}
        <div className="mt-auto pt-2.5">
          {outOfStock ? (
            <button
              type="button"
              disabled
              className="h-9 w-full rounded-xl bg-slate-100 text-xs font-bold text-slate-400"
            >
              Out of stock
            </button>
          ) : (
            <button
              type="button"
              onClick={() => add(product.id, 1)}
              disabled={busy}
              aria-label={`Add ${product.name} to cart`}
              className="h-9 w-full rounded-xl bg-brand-600 text-xs font-bold text-white transition hover:bg-brand-700 disabled:opacity-60"
            >
              Add
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
