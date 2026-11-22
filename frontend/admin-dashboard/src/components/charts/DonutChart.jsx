/** Simple donut for splits like COD vs UPI. Data: [{ label, value, color }]. */
export default function DonutChart({ data = [], size = 148, thickness = 20, centerLabel, centerValue }) {
  const total = data.reduce((sum, d) => sum + (Number(d.value) || 0), 0);
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;

  if (!total) {
    return <p className="py-10 text-center text-xs text-slate-400">No data yet.</p>;
  }

  let offset = 0;

  return (
    <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-center sm:gap-5">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Distribution chart">
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          {data.map((d) => {
            const fraction = (Number(d.value) || 0) / total;
            const dash = fraction * circumference;
            const circle = (
              <circle
                key={d.label}
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={d.color}
                strokeWidth={thickness}
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offset}
              >
                <title>{`${d.label}: ${d.value}`}</title>
              </circle>
            );
            offset += dash;
            return circle;
          })}
        </g>
        {(centerValue !== undefined || centerLabel) && (
          <>
            <text x="50%" y="46%" textAnchor="middle" className="fill-slate-900" style={{ fontSize: 18, fontWeight: 800 }}>
              {centerValue}
            </text>
            <text x="50%" y="60%" textAnchor="middle" className="fill-slate-400" style={{ fontSize: 9, textTransform: "uppercase" }}>
              {centerLabel}
            </text>
          </>
        )}
      </svg>

      <ul className="space-y-1.5 text-xs">
        {data.map((d) => (
          <li key={d.label} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: d.color }} aria-hidden="true" />
            <span className="text-slate-600">{d.label}</span>
            <span className="font-semibold text-slate-900">{d.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
