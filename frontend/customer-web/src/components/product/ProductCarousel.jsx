import { useRef } from "react";
import ProductCard from "./ProductCard";

/** Horizontally scrolling rail used on the home page. */
export default function ProductCarousel({ title, subtitle, products = [], action }) {
  const railRef = useRef(null);

  const scrollBy = (dir) => {
    const el = railRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * (el.clientWidth * 0.8), behavior: "smooth" });
  };

  if (!products.length) return null;

  return (
    <section className="container-page mt-8">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 className="section-title">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p> : null}
        </div>
        <div className="flex items-center gap-1.5">
          {action}
          <button
            type="button"
            onClick={() => scrollBy(-1)}
            aria-label="Scroll left"
            className="hidden h-8 w-8 place-items-center rounded-full bg-white text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 sm:grid"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={() => scrollBy(1)}
            aria-label="Scroll right"
            className="hidden h-8 w-8 place-items-center rounded-full bg-white text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 sm:grid"
          >
            ›
          </button>
        </div>
      </div>

      {/* The rail bleeds to the container edge on purpose (so the next card
          peeks), but the negative margin only cancels the container's own
          padding - it must not run past it. Cards use a calc width so the gap
          is subtracted from the track, keeping every card the same size and
          the first/last flush with the section heading above. */}
      <div
        ref={railRef}
        className="no-scrollbar -mx-1 flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-2 pt-0.5"
      >
        {products.map((p) => (
          <div
            key={p.id}
            className="shrink-0 snap-start basis-[calc(50%-0.375rem)] sm:basis-[calc(33.333%-0.5rem)] lg:basis-[calc(25%-0.5625rem)] xl:basis-[calc(20%-0.6rem)]"
          >
            <ProductCard product={p} />
          </div>
        ))}
        {/* Trailing spacer so the last card never sits flush to the edge */}
        <div className="w-1 shrink-0" aria-hidden="true" />
      </div>
    </section>
  );
}
