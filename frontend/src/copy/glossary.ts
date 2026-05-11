// Single source of truth for Irish-tax + pension jargon. Used by <JargonTerm/>.
// Add a term here, then use <JargonTerm term="PRSI" /> anywhere it appears in copy.
//
// Keep definitions short (one sentence + optional rate/threshold). Longer
// explanations belong in inline help, not the glossary tooltip.

export type GlossaryKey =
  | "PRSI"
  | "USC"
  | "PAYE"
  | "CAT"
  | "CGT"
  | "ETF_EXIT_TAX"
  | "ARF"
  | "AVC"
  | "PRSA"
  | "OCCUPATIONAL_PENSION"
  | "STATE_PENSION"
  | "RENT_CREDIT"
  | "LUMP_SUM"
  | "MARGINAL_RATE";

interface GlossaryEntry {
  short: string; // 1–6 word label shown if children prop not supplied
  body: string; // 1–2 sentence definition shown on hover
}

export const GLOSSARY: Record<GlossaryKey, GlossaryEntry> = {
  PRSI: {
    short: "PRSI",
    body: "Pay Related Social Insurance. A 4.1% charge on most earnings that funds social welfare, including the State Pension.",
  },
  USC: {
    short: "USC",
    body: "Universal Social Charge. A second, progressive tax on gross income (0.5%–8%) applied alongside income tax.",
  },
  PAYE: {
    short: "PAYE",
    body: "Pay As You Earn. The system Irish employers use to deduct income tax, USC, and PRSI directly from your salary.",
  },
  CAT: {
    short: "CAT",
    body: "Capital Acquisitions Tax. A 33% tax on inheritances and gifts above the recipient's lifetime threshold (Group A €400k, B €40k, C €20k).",
  },
  CGT: {
    short: "CGT",
    body: "Capital Gains Tax. A 33% tax on the gain when you sell an investment or property (excluding your main home).",
  },
  ETF_EXIT_TAX: {
    short: "ETF exit tax",
    body: "Irish exit tax on ETFs/funds — 41% on gains at disposal or every 8 years (deemed disposal). No CGT loss relief.",
  },
  ARF: {
    short: "ARF",
    body: "Approved Retirement Fund. A pension pot you draw from in retirement, with a mandatory minimum drawdown (4–5% of value/yr).",
  },
  AVC: {
    short: "AVC",
    body: "Additional Voluntary Contribution. Extra pension contributions on top of an occupational scheme, sharing the same age-based tax-relief cap.",
  },
  PRSA: {
    short: "PRSA",
    body: "Personal Retirement Savings Account. A private pension wrapper — contributions get income-tax relief up to age-based limits.",
  },
  OCCUPATIONAL_PENSION: {
    short: "Occupational pension",
    body: "Employer-sponsored pension scheme. Employer + employee contributions; tax-relieved up to the age-based earnings cap.",
  },
  STATE_PENSION: {
    short: "State Pension",
    body: "Contributory pension paid from age 66 to anyone with sufficient PRSI record (~€14,000/yr at full rate, 2026).",
  },
  RENT_CREDIT: {
    short: "Rent Tax Credit",
    body: "A €1,000/yr credit reducing income tax for renters paying for their primary residence.",
  },
  LUMP_SUM: {
    short: "Tax-free lump sum",
    body: "At retirement, you can take 25% of your pension as a lump sum. First €200k is tax-free; next €300k taxed at 20%; above at marginal rate.",
  },
  MARGINAL_RATE: {
    short: "Marginal rate",
    body: "The income-tax rate on your next euro of income — 20% in the standard band, 40% above it. Drives the value of pension tax relief.",
  },
};
