/** Friendly "nothing here" panel with an optional action. */
export default function EmptyState({ icon, title, description, action, className = "" }) {
  return (
    <div className={`card flex flex-col items-center justify-center px-6 py-14 text-center ${className}`}>
      {icon ? (
        <div className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-700">
          {icon}
        </div>
      ) : null}
      <h2 className="text-base font-bold text-slate-900">{title}</h2>
      {description ? (
        <p className="mt-1.5 max-w-sm text-sm text-slate-600">{description}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
