/**
 * Dependency-free SVG bar chart.
 *
 * Deliberately hand-rolled: the dashboard needs three simple charts, and a
 * charting library would add ~100 kB to the bundle for no benefit. Values come
 * from the API via props - nothing is simulated.
 */
export default function BarChart({ data = [], height = 180, valueFormat = (v) => v, labelKey = "label", valueKey = "value", color = "#4f46e5", ariaLabel = "Bar chart" }) {
  if (!data.length) {
    return <p className="py-10 text-center text-xs text-slate-400">No data to chart yet.</p>;
  }

  const max = Math.max(...data.map((d) => Number(d[valueKey]) || 0), 1);
  const barWidth = 100 / data.length;

  return (
    <figure className="w-full">
      <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" role="img" aria-label={ariaLabel} className="h-44 w-full">
        {[0.25, 0.5, 0.75, 1].map((g) => (
          <line key={g} x1="0" x2="100" y1={height - height * g} y2={height - height * g} stroke="#e2e8f0" strokeWidth="0.5" vectorEffect="non-scaling-stroke" />
        ))}
        {data.map((d, i) => {
          const value = Number(d[valueKey]) || 0;
          const h = (value / max) * (height - 16);
          return (
            <rect
              key={i}
              x={i * barWidth + barWidth * 0.18}
              y={height - h}
              width={barWidth * 0.64}
              height={Math.max(h, value > 0 ? 1.5 : 0)}
              rx="1"
              fill={color}
              opacity={d.muted ? 0.35 : 1}
            >
              <title>{`${d[labelKey]}: ${valueFormat(value)}`}</title>
            </rect>
          );
        })}
      </svg>
      <figcaption className="mt-2 flex justify-between gap-1 text-[10px] text-slate-500">
        {data.map((d, i) => (
          <span key={i} className="flex-1 truncate text-center">{d[labelKey]}</span>
        ))}
      </figcaption>
    </figure>
  );
}
