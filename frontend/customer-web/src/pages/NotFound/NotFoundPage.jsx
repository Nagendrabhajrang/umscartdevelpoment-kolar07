import { Link } from "react-router-dom";

/** 404. The catch-all route redirects here. */
export default function NotFoundPage() {
  return (
    <div className="container-page py-16">
      <div className="mx-auto max-w-md text-center">
        <p className="text-6xl font-extrabold tracking-tight text-brand-600">404</p>
        <h1 className="mt-2 text-xl font-extrabold text-slate-900">This page does not exist</h1>
        <p className="mt-1.5 text-sm text-slate-600">
          The link may be broken, or the page may have moved. Everything the store
          stocks is one tap away.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2.5">
          <Link
            to="/"
            className="inline-flex h-11 items-center rounded-xl bg-brand-600 px-5 text-sm font-bold text-white hover:bg-brand-700"
          >
            Go home
          </Link>
          <Link
            to="/products"
            className="inline-flex h-11 items-center rounded-xl bg-white px-5 text-sm font-bold text-slate-800 ring-1 ring-inset ring-slate-300 hover:bg-slate-50"
          >
            Browse products
          </Link>
        </div>
      </div>
    </div>
  );
}
