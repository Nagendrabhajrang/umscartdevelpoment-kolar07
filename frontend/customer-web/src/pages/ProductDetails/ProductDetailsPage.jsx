import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useFetch } from "../../hooks";
import { catalogService } from "../../services/catalogService";
import { useCart } from "../../context/CartContext";
import ProductCarousel from "../../components/product/ProductCarousel";
import QuantityStepper from "../../components/common/QuantityStepper";
import Button from "../../components/common/Button";
import Badge from "../../components/common/Badge";
import Skeleton from "../../components/common/Skeleton";
import ErrorState from "../../components/common/ErrorState";
import { formatMoney } from "../../utils/format";

/** Single product: gallery-ish image, price block, quantity, add to cart. */
export default function ProductDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { add, quantityFor, busyProduct } = useCart();
  const [qty, setQty] = useState(1);

  const { data: product, loading, error, reload } = useFetch(() => catalogService.getProduct(id), [id]);
  const related = useFetch(() => catalogService.getRelated(id), [id]);

  if (loading) {
    return (
      <div className="container-page py-6">
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="aspect-square w-full rounded-2xl" />
          <div className="space-y-3">
            <Skeleton className="h-7 w-3/4" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-10 w-1/2" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="container-page py-10">
        <ErrorState error={error} onRetry={reload} title="That product could not be loaded" />
      </div>
    );
  }

  const inCart = quantityFor(product.id);
  const busy = busyProduct === product.id;
  const outOfStock = product.in_stock === false;
  const image = product.primary_image || product.image_url;
  const discount = Math.round(Number(product.discount_percent) || 0);

  return (
    <div className="container-page py-5">
      <nav className="mb-4 flex flex-wrap items-center gap-1.5 text-xs text-slate-500" aria-label="Breadcrumb">
        <Link to="/" className="hover:text-brand-700">Home</Link>
        <span aria-hidden="true">/</span>
        <Link to="/products" className="hover:text-brand-700">Products</Link>
        {product.category_name ? (
          <>
            <span aria-hidden="true">/</span>
            <Link to={`/products?category=${product.category}`} className="hover:text-brand-700">
              {product.category_name}
            </Link>
          </>
        ) : null}
      </nav>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Image */}
        <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-4">
          {image ? (
            <img src={image} alt={product.name} className="mx-auto aspect-square w-full max-w-md object-contain" />
          ) : (
            <div className="grid aspect-square place-items-center text-slate-300">
              <svg viewBox="0 0 24 24" className="h-16 w-16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="m21 15-5-5L5 21" />
              </svg>
            </div>
          )}
          {discount > 0 ? (
            <span className="absolute left-4 top-4 rounded-lg bg-brand-600 px-2 py-1 text-xs font-bold text-white">
              {discount}% OFF
            </span>
          ) : null}
        </div>

        {/* Buy box */}
        <div>
          <div className="flex flex-wrap items-center gap-1.5">
            {product.brand ? <Badge tone="info">{product.brand}</Badge> : null}
            {product.is_vegetarian ? <Badge tone="success">Veg</Badge> : null}
            {product.category_name ? <Badge>{product.category_name}</Badge> : null}
            {outOfStock ? <Badge tone="danger">Out of stock</Badge> : null}
          </div>

          <h1 className="mt-2.5 text-2xl font-extrabold leading-tight tracking-tight text-slate-900">
            {product.name}
          </h1>
          <p className="mt-1 text-sm text-slate-500">{product.unit_label}</p>

          <div className="mt-4 flex items-end gap-2.5">
            <span className="text-3xl font-extrabold text-slate-900">{formatMoney(product.selling_price)}</span>
            {Number(product.mrp) > Number(product.selling_price) ? (
              <>
                <span className="pb-1 text-sm text-slate-400 line-through">{formatMoney(product.mrp)}</span>
                <span className="pb-1 text-sm font-bold text-brand-700">
                  Save {formatMoney(Number(product.mrp) - Number(product.selling_price))}
                </span>
              </>
            ) : null}
          </div>
          <p className="mt-1 text-xs text-slate-500">Inclusive of all taxes</p>

          {typeof product.available_quantity === "number" && !outOfStock ? (
            <p className="mt-2 text-xs font-semibold text-slate-600">
              {product.available_quantity > 10
                ? "In stock"
                : `Only ${product.available_quantity} left`}
            </p>
          ) : null}

          {/* Quantity + add */}
          <div className="mt-5 flex flex-wrap items-center gap-2.5">
            <QuantityStepper
              value={qty}
              onChange={(v) => setQty(Math.max(1, v))}
              max={Math.min(99, product.available_quantity || 99)}
              disabled={outOfStock}
            />
            <Button
              size="lg"
              onClick={() => add(product.id, qty)}
              loading={busy}
              disabled={outOfStock}
              className="flex-1 sm:flex-none"
            >
              {outOfStock ? "Out of stock" : inCart > 0 ? `Add ${qty} more (${inCart} in cart)` : "Add to cart"}
            </Button>
            <Button size="lg" variant="secondary" as={Link} to="/cart">
              Go to cart
            </Button>
          </div>

          {inCart > 0 ? (
            <button
              type="button"
              onClick={() => navigate("/cart")}
              className="mt-3 text-sm font-semibold text-brand-700 hover:underline"
            >
              Go to cart ({inCart}) →
            </button>
          ) : null}

          {product.description ? (
            <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-bold text-slate-900">About this product</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{product.description}</p>
            </div>
          ) : null}

          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 rounded-2xl border border-slate-200 bg-white p-4 text-sm">
            {[
              ["SKU", product.sku],
              ["Unit", product.unit_label],
              ["Category", product.category_name || product.parent_category],
              ["Brand", product.brand],
            ]
              .filter(([, v]) => v)
              .map(([k, v]) => (
                <div key={k}>
                  <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{k}</dt>
                  <dd className="text-sm text-slate-700">{v}</dd>
                </div>
              ))}
          </dl>
        </div>
      </div>

      <ProductCarousel
        title="Often bought with this"
        products={related.data?.results ?? related.data ?? []}
      />
    </div>
  );
}
