export default function Spinner({ size = "md", className = "" }) {
  const sizes = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-9 w-9" };
  return (
    <span role="status" aria-label="Loading" className={`inline-block ${className}`}>
      <svg className={`animate-spin text-brand-600 ${sizes[size]}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
        <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v3a5 5 0 00-5 5H4z" />
      </svg>
    </span>
  );
}
