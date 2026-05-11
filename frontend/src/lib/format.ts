const eur = new Intl.NumberFormat("en-IE", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const pct = new Intl.NumberFormat("en-IE", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 2,
});

export const fmtMoney = (n: number) => eur.format(n);
export const fmtPct = (n: number) => pct.format(n);

/**
 * Compact percentage display for table cells and labels.
 * Strips trailing zeros: 0.025 → "2.5%", 0.03 → "3%", 0.125 → "12.5%", 0.125 → "12.5%"
 * Pass the fractional value (0–1), not the already-multiplied display value.
 */
export function fmtPctDisplay(v: number): string {
  // toPrecision(6) removes float noise; parseFloat strips trailing zeros; no Intl overhead.
  return `${parseFloat((v * 100).toPrecision(6))}%`;
}
