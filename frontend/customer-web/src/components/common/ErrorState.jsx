/** Shown when a page's data request fails. Always offers a retry. */
export default function ErrorState({ error, onRetry, title = "That did not load" }) {
  const message =
    error?.message || "Something went wrong while talking to the server.";
  return (
    <div className="card border-rose-200 bg-rose-50/60 px-6 py-10 text-center">
      <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-rose-100 text-rose-700">
        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
        </svg>
      </div>
      <h2 className="text-base font-bold text-rose-900">{title}</h2>
      <p className="mx-auto mt-1.5 max-w-md text-sm text-rose-800">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 inline-flex h-10 items-center rounded-xl bg-rose-600 px-5 text-sm font-semibold text-white hover:bg-rose-700"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
