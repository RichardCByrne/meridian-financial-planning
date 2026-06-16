/**
 * Small inline spinner for in-progress button actions. Inherits the button's
 * text colour (`currentColor`), so it works on both primary and secondary
 * buttons without extra styling.
 */
export function Spinner({ size = 14 }: { size?: number }) {
  return (
    <span
      className="meridian-spinner"
      role="status"
      aria-label="Loading"
      style={{ width: size, height: size, borderWidth: Math.max(2, Math.round(size / 7)) }}
    />
  );
}
