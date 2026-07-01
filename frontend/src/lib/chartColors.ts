// Chart palette — derived from the Meridian brand tokens in index.css (:root).
// recharts takes colours as string props (SVG fill/stroke), so these cannot be
// CSS custom properties; keep them in sync with the tokens by hand. Brass
// (--brass) is deliberately absent: it is a signature accent (compass ticks)
// only, never a data series.
export const CHART = {
  ink: "#0b1f2a", // --ink — deterministic / reference lines
  teal: "#0e6e62", // --accent — primary series (median, net worth)
  fanOuter: "#cfe4df", // pale teal wash — p5–25 / 75–95 band
  fanInner: "#a9d0c8", // deeper teal wash — p25–75 band
  gain: "#15803d", // --gain — income / liquid / positive
  loss: "#b91c1c", // --loss — expenses / debt / negative
  neutral: "#5c6b6e", // --muted — supporting bars (assets drawn)
  grid: "#d6d8ce", // --line — cartesian grid rules
};

// Categorical ramp for multi-series charts (income kinds, tax components).
// Cartographic map-legend hues chosen to harmonise with the meridian teal and
// stay legible when stacked. Teal leads; the rest are marine, sage, clay,
// heather, light-teal and ochre — none of them brass.
export const CHART_SERIES = [
  "#0e6e62", // teal
  "#1f6f8b", // marine
  "#6a8f6b", // sage
  "#b5673f", // clay
  "#7c6a9c", // heather
  "#3f8f83", // light teal
  "#9c7b3f", // ochre
];
