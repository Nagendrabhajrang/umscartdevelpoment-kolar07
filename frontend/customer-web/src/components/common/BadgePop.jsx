/** Keyframes used by the header badge; injected once, no runtime cost. */
export default function BadgeStyles() {
  return (
    <style>{`@keyframes badge-pop { from { transform: scale(.4) } to { transform: scale(1) } }`}</style>
  );
}
