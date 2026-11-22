export default function EmptyState({ icon: Icon, title, description, action, compact = false }) {
  return (
    <div className={`flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white text-center ${compact ? "px-4 py-8" : "px-6 py-14"}`}>
      {Icon && (
        <span className="mb-3 grid h-12 w-12 place-items-center rounded-full bg-slate-100 text-slate-400">
          <Icon className="h-6 w-6" aria-hidden="true" />
        </span>
      )}
      <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-xs text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
