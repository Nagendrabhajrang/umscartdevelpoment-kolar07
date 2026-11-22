import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

/**
 * Hero banner carousel.
 *
 * Drives every live banner whose ``placement`` is ``hero`` (as returned by
 * ``GET /banners/live/``). Slides auto-advance, can be swiped on touch, and
 * respond to the arrow keys, the dots and the prev/next arrows.
 *
 * Each banner's own ``title`` / ``subtitle`` / ``image_url`` are used when
 * present; the gradient + copy fallback keeps the panel looking right when a
 * banner row has no artwork.
 *
 * NOTE: no ``AnimatePresence mode="wait"`` here - this store deliberately
 * avoids it. Slides cross-fade with plain CSS on absolutely-stacked layers.
 */
const FALLBACK = {
  title: "Fresh groceries in 45 minutes",
  subtitle: "Fruit, dairy, staples and everyday essentials from your neighbourhood store.",
  link: "/products",
};

const GRADIENTS = [
  "from-brand-600 via-brand-700 to-emerald-800",
  "from-emerald-600 via-teal-700 to-emerald-900",
  "from-amber-500 via-orange-600 to-rose-700",
  "from-sky-600 via-blue-700 to-indigo-800",
  "from-fuchsia-600 via-purple-700 to-violet-900",
];

function bannerLink(banner) {
  if (!banner) return FALLBACK.link;
  // The API resolves link_type + target into one path already.
  if (banner.resolved_link) return banner.resolved_link;
  if (banner.link_type === "product" && banner.linked_product) return `/products/${banner.linked_product}`;
  if (banner.link_type === "category" && banner.linked_category) return `/category/${banner.linked_category}`;
  return banner.link_url || FALLBACK.link;
}

export default function HeroCarousel({ banners = [], loading = false, intervalMs = 5000 }) {
  const slides = banners.length ? banners : [null]; // null => fallback panel
  const count = slides.length;

  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const touchX = useRef(null);
  const timer = useRef(null);

  // Clamp when the data changes underneath us.
  useEffect(() => {
    setIndex((i) => (i >= count ? 0 : i));
  }, [count]);

  const go = useCallback(
    (next) => setIndex(((next % count) + count) % count),
    [count],
  );
  const next = useCallback(() => go(index + 1), [go, index]);
  const prev = useCallback(() => go(index - 1), [go, index]);

  // Auto-advance. Stopped while hovered/focused and when there is one slide.
  useEffect(() => {
    if (count < 2 || paused) return undefined;
    timer.current = setTimeout(next, intervalMs);
    return () => clearTimeout(timer.current);
  }, [count, paused, next, intervalMs]);

  const onKeyDown = (e) => {
    if (e.key === "ArrowRight") { e.preventDefault(); next(); }
    if (e.key === "ArrowLeft") { e.preventDefault(); prev(); }
  };

  const onTouchStart = (e) => { touchX.current = e.touches[0].clientX; };
  const onTouchEnd = (e) => {
    if (touchX.current == null) return;
    const dx = e.changedTouches[0].clientX - touchX.current;
    touchX.current = null;
    if (Math.abs(dx) < 40) return;
    if (dx < 0) next(); else prev();
  };

  return (
    <section className="container-page pt-4">
      <div
        className="group relative overflow-hidden rounded-3xl bg-slate-900 shadow-sm"
        role="region"
        aria-roledescription="carousel"
        aria-label="Featured offers"
        tabIndex={0}
        onKeyDown={onKeyDown}
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        onFocus={() => setPaused(true)}
        onBlur={() => setPaused(false)}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {/* Layers: every slide is stacked and cross-faded by opacity. */}
        <div className="relative h-[210px] sm:h-[260px] lg:h-[300px]">
          {slides.map((banner, i) => {
            const active = i === index;
            const image = banner?.image_url || banner?.image || null;
            const mobileImage = banner?.mobile_image_url || banner?.mobile_image || null;
            const gradient = GRADIENTS[i % GRADIENTS.length];
            const title = banner?.title || FALLBACK.title;
            const subtitle = banner?.subtitle || FALLBACK.subtitle;
            const href = bannerLink(banner);
            const hasArt = Boolean(image);

            return (
              <div
                key={banner?.id ?? "fallback"}
                className={`absolute inset-0 transition-opacity duration-700 ease-out ${
                  active ? "opacity-100" : "pointer-events-none opacity-0"
                }`}
                aria-hidden={!active}
                role="group"
                aria-roledescription="slide"
                aria-label={`${i + 1} of ${count}`}
              >
                {/* Artwork */}
                {hasArt ? (
                  <>
                    {mobileImage ? (
                      <>
                        <img src={mobileImage} alt={banner?.alt_text || title}
                          className="absolute inset-0 h-full w-full object-cover sm:hidden" loading={i === 0 ? "eager" : "lazy"} />
                        <img src={image} alt={banner?.alt_text || title}
                          className="absolute inset-0 hidden h-full w-full object-cover sm:block" loading={i === 0 ? "eager" : "lazy"} />
                      </>
                    ) : (
                      <img src={image} alt={banner?.alt_text || title}
                        className="absolute inset-0 h-full w-full object-cover" loading={i === 0 ? "eager" : "lazy"} />
                    )}
                    {/* Readability scrim: a soft left-to-right wash plus a gentle
                        bottom lift, so the artwork stays visible while the copy
                        keeps its contrast. */}
                    <div className="absolute inset-0 bg-gradient-to-r from-slate-950/75 via-slate-900/30 to-slate-900/5" />
                    <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-slate-950/45 to-transparent" />
                  </>
                ) : (
                  <div className={`absolute inset-0 bg-gradient-to-br ${gradient}`} />
                )}

                {/* Copy */}
                <div className="relative z-10 flex h-full items-center">
                  <div className="w-full max-w-xl px-6 sm:px-10">
                    <p className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-[11px] font-bold uppercase tracking-wide text-white ring-1 ring-inset ring-white/25 backdrop-blur-sm">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
                      {banner ? banner.placement_display || "Featured" : "Delivering now"}
                    </p>
                    <h1 className="mt-3 text-2xl font-extrabold leading-tight tracking-tight text-white sm:text-3xl lg:text-4xl">
                      {title}
                    </h1>
                    {subtitle && (
                      <p className="mt-2 max-w-md text-xs text-white/85 sm:text-sm lg:text-base">{subtitle}</p>
                    )}
                    <Link
                      to={href}
                      className="mt-4 inline-flex h-10 items-center rounded-xl bg-white px-4 text-xs font-bold text-brand-800 shadow-sm transition hover:bg-brand-50 sm:h-11 sm:px-5 sm:text-sm"
                      tabIndex={active ? 0 : -1}
                    >
                      Shop now
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {loading && (
          <div className="absolute inset-0 animate-pulse bg-slate-800" aria-hidden="true" />
        )}

        {/* Arrows */}
        {count > 1 && (
          <>
            <button
              type="button"
              onClick={prev}
              aria-label="Previous banner"
              className="absolute left-2 top-1/2 z-20 hidden h-9 w-9 -translate-y-1/2 place-items-center rounded-full bg-white/85 text-slate-800 shadow-md backdrop-blur transition hover:bg-white sm:grid sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100"
            >
              <span aria-hidden="true" className="text-lg leading-none">‹</span>
            </button>
            <button
              type="button"
              onClick={next}
              aria-label="Next banner"
              className="absolute right-2 top-1/2 z-20 hidden h-9 w-9 -translate-y-1/2 place-items-center rounded-full bg-white/85 text-slate-800 shadow-md backdrop-blur transition hover:bg-white sm:grid sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100"
            >
              <span aria-hidden="true" className="text-lg leading-none">›</span>
            </button>
          </>
        )}

        {/* Dots */}
        {count > 1 && (
          <div className="absolute inset-x-0 bottom-3 z-20 flex items-center justify-center gap-1.5">
            {slides.map((b, i) => (
              <button
                key={b?.id ?? i}
                type="button"
                onClick={() => go(i)}
                aria-label={`Go to banner ${i + 1}`}
                aria-current={i === index}
                className={`h-1.5 rounded-full transition-all ${
                  i === index ? "w-6 bg-white" : "w-1.5 bg-white/50 hover:bg-white/80"
                }`}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
