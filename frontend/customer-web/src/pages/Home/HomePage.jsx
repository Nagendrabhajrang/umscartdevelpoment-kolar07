import { Link } from "react-router-dom";
import { useFetch } from "../../hooks";
import { bannerService } from "../../services/bannerService";
import { catalogService } from "../../services/catalogService";
import { useStore } from "../../context/StoreContext";
import ProductCarousel from "../../components/product/ProductCarousel";
import HeroCarousel from "../../components/home/HeroCarousel";
import Skeleton, { SkeletonCard } from "../../components/common/Skeleton";

/**
 * Storefront home: hero, category rail, offer strip, then three product rails.
 *
 * Every section fetches independently so one slow or failing endpoint cannot
 * blank the page — a failed rail simply does not render.
 */
export default function HomePage() {
  const { settings } = useStore();

  const banners = useFetch(() => bannerService.getLive(), []);
  const categories = useFetch(() => catalogService.getCategoryTree(), []);
  const featured = useFetch(() => catalogService.getFeatured({ page_size: 12 }), []);
  const newest = useFetch(() => catalogService.getProducts({ page_size: 12, ordering: "-created_at" }), []);
  // The API cannot sort by discount_percent, so the savings rail is built from the
    // newest page and sorted here. Fetching 40 keeps the top 12 meaningful.
    const discounted = useFetch(
      () =>
        catalogService
          .getProducts({ page_size: 40, ordering: "-created_at" })
          .then((page) => ({
            ...page,
            results: [...(page.results ?? [])]
              .sort((a, b) => Number(b.discount_percent || 0) - Number(a.discount_percent || 0))
              .slice(0, 12),
          })),
      [],
    );

  // Every live hero banner, in display order - the carousel cycles them all.
  const heroBanners = (banners.data || [])
    .filter((b) => b.placement === "hero")
    .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
  const stripBanners = banners.data?.filter((b) => b.placement === "strip") ?? [];
  const topCategories = (categories.data ?? []).slice(0, 10);

  return (
    <div className="pb-4">
      {/* ---------------- Hero carousel (all live hero banners) ---------------- */}
      <HeroCarousel
        banners={heroBanners}
        loading={banners.loading}
      />

      {/* ---------------- Categories ---------------- */}
      <section className="container-page mt-8">
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="section-title">Shop by category</h2>
            <p className="mt-0.5 text-xs text-slate-500">Everything the store stocks, grouped</p>
          </div>
          <Link to="/categories" className="link-quiet">
            All categories →
          </Link>
        </div>

        {categories.loading ? (
          <div className="grid grid-cols-4 gap-2.5 sm:grid-cols-6 lg:grid-cols-10">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="flex flex-col items-center gap-2">
                <Skeleton className="h-16 w-16 rounded-2xl" />
                <Skeleton className="h-2.5 w-12" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-2.5 sm:grid-cols-6 lg:grid-cols-10">
            {topCategories.map((c) => (
              <Link
                key={c.id}
                to={`/products?category=${c.id}`}
                className="group flex flex-col items-center gap-2 rounded-2xl bg-white p-2.5 text-center shadow-card ring-1 ring-slate-100 transition hover:-translate-y-0.5 hover:shadow-card-hover"
              >
                <span className="grid h-14 w-14 place-items-center overflow-hidden rounded-xl bg-slate-50 ring-1 ring-slate-100 transition group-hover:ring-brand-300">
                  {c.image ? (
                    <img src={c.image} alt="" className="h-full w-full object-cover" loading="lazy" />
                  ) : (
                    <span className="text-lg font-bold text-brand-600">{c.name?.[0]}</span>
                  )}
                </span>
                <span className="line-clamp-2 text-[11px] font-semibold leading-tight text-slate-700">
                  {c.name}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* ---------------- Rails ---------------- */}
      {featured.loading ? (
        <RailSkeleton title="Bestsellers" />
      ) : (
        <ProductCarousel
          title="Bestsellers"
          subtitle="What the neighbourhood is buying"
          products={featured.data?.results ?? []}
          action={
            <Link to="/products" className="link-quiet">
              See all →
            </Link>
          }
        />
      )}

      {discounted.loading ? (
        <RailSkeleton title="Biggest savings" />
      ) : (
        <ProductCarousel
          title="Biggest savings"
          subtitle="Top discounts today"
          products={discounted.data?.results ?? []}
        />
      )}

      {newest.loading ? (
        <RailSkeleton title="Just arrived" />
      ) : (
        <ProductCarousel
          title="Just arrived"
          subtitle="Freshly added to the catalogue"
          products={newest.data?.results ?? []}
        />
      )}

      {/* ---------------- Trust row ---------------- */}
      <section className="container-page mt-10">
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ["45-minute delivery", "Straight from the nearest store"],
            ["Cash on delivery", "Pay when the bag is in your hand"],
            ["Freshness promise", "Not happy? We refund that item"],
          ].map(([title, text]) => (
            <div key={title} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card transition-shadow hover:shadow-card-hover">
              <p className="text-sm font-bold text-slate-900">{title}</p>
              <p className="mt-1 text-xs text-slate-600">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {stripBanners.length ? (
        <section className="container-page mt-8">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {stripBanners.slice(0, 3).map((b) => (
              <Link
                key={b.id}
                to={b.link_type === "coupon" ? "/products" : b.resolved_link || "/products"}
                className="group flex overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card transition-shadow hover:shadow-card-hover"
              >
                {b.image_url ? (
                  <img
                    src={b.image_url}
                    alt={b.alt_text || b.title}
                    className="h-full w-28 shrink-0 object-cover"
                    loading="lazy"
                  />
                ) : null}
                <div className="flex min-w-0 flex-col justify-center p-3.5">
                  <p className="truncate text-sm font-bold text-slate-900 group-hover:text-brand-700">{b.title}</p>
                  {b.subtitle ? <p className="mt-0.5 line-clamp-2 text-xs text-slate-600">{b.subtitle}</p> : null}
                </div>
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function RailSkeleton({ title }) {
  return (
    <section className="container-page mt-8">
      <h2 className="section-title mb-3">{title}</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </section>
  );
}
