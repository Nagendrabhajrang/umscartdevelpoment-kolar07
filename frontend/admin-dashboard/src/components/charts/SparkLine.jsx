/** Tiny inline trend line for stat cards. Pure SVG, no dependencies. */
export default function SparkLine({ values = [], width = 96, height = 28, color = "#4f46e5" }) {
  if (values.length < 2) return null;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * width},${height - ((v - min) / span) * (height - 4) - 2}`)
    .join(" ");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" className="overflow-visible">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
