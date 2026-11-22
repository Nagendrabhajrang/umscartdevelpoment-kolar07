import { Link } from "react-router-dom";
import { useFetch } from "../../hooks";
import { catalogService } from "../../services/catalogService";
import Skeleton from "../../components/common/Skeleton";
import ErrorState from "../../components/common/ErrorState";

/** Every category as a card, with its children listed underneath. */
export default function CategoriesPage() {
  const { data, loading, error, reload } = useFetch(() => catalogService.getCategoryTree(), []);
  const categories = data ?? [];

  return (
    <div className="container-page py-6">
      <header className="mb-5">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Categories</h1>
        <p className="mt-1 text-sm text-slate-600">Browse everything the store stocks.</p>
      </header>

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-2xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {categories.map((c) => (
            <div key={c.id} className="card flex flex-col overflow-hidden p-0">
              <Link to={`/products?category=${c.id}`} className="block">
                <div className="flex items-center gap-3 p-3.5">
                  <span className="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-xl bg-brand-50">
                    {c.image ? (
                      <img src={c.image} alt="" className="h-full w-full object-cover" loading="lazy" />
                    ) : (
                      <span className="text-lg font-bold text-brand-600">{c.name?.[0]}</span>
                    )}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold text-slate-900">{c.name}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      {c.child_count ? `${c.child_count} sub-categories` : `${c.product_count || 0} products`}
                    </p>
                  </div>
                </div>
              </Link>

              {c.children?.length ? (
                <ul className="mt-auto space-y-1 border-t border-slate-100 px-3.5 py-2.5">
                  {c.children.slice(0, 3).map((child) => (
                    <li key={child.id}>
                      <Link
                        to={`/products?category=${child.id}`}
                        className="text-xs text-slate-600 hover:text-brand-700 hover:underline"
                      >
                        {child.name}
                      </Link>
                    </li>
                  ))}
                  {c.children.length > 3 ? (
                    <li className="text-[11px] text-slate-400">+{c.children.length - 3} more</li>
                  ) : null}
                </ul>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
