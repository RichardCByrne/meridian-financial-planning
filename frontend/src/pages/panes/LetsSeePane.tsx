import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  useAssets,
  useAssumptions,
  useGoals,
  useMonteCarlo,
  usePeople,
  usePlan,
  useProjection,
} from "../../api/hooks";
import type { Goal, MonteCarloResponse, YearRow } from "../../api/types";
import { fmtMoney } from "../../lib/format";
import { JargonTerm } from "../../components/JargonTerm";
import { ChartSkeleton } from "../../components/Skeleton";
import { useIsMobile } from "../../hooks/useIsMobile";

type ChartKind = "net_worth" | "cash_flow" | "income_vs_expenses" | "tax";

const CHART_OPTIONS: { value: ChartKind; label: string }[] = [
  { value: "net_worth", label: "Net worth" },
  { value: "cash_flow", label: "Cash flow (income vs expenses)" },
  { value: "income_vs_expenses", label: "Income breakdown" },
  { value: "tax", label: "Tax breakdown" },
];

const TAX_COLORS = { income_tax: "#2563eb", usc: "#7c3aed", prsi: "#0ea5e9" };
const KIND_COLORS = ["#2563eb", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#7c3aed", "#ec4899"];

const REAL_TOGGLE_KEY = (id: number) => `meridian:letsSee:real:${id}`;
const MC_N_KEY = (id: number) => `meridian:letsSee:mcN:${id}`;

export function LetsSeePane({ planId }: { planId: number }) {
  const { data, isLoading, error } = useProjection(planId);
  const { data: plan } = usePlan(planId);
  const { data: assumptions } = useAssumptions(planId);
  const { data: people } = usePeople(planId);
  const { data: goals } = useGoals(planId);
  const { data: assets } = useAssets(planId);
  const isMobile = useIsMobile();
  const tooltipTrigger = isMobile ? "click" : "hover";
  const [chart, setChart] = useState<ChartKind>("net_worth");
  const [hoverYear, setHoverYear] = useState<number | null>(null);
  const [showMonteCarlo, setShowMonteCarlo] = useState(false);
  const [realMode, setRealMode] = useState<boolean>(() => {
    try {
      return localStorage.getItem(REAL_TOGGLE_KEY(planId)) === "1";
    } catch {
      return false;
    }
  });
  const [mcN, setMcN] = useState<number>(() => {
    try {
      const v = Number(localStorage.getItem(MC_N_KEY(planId)));
      return [50, 200, 1000].includes(v) ? v : 200;
    } catch {
      return 200;
    }
  });
  const [mcSeedText, setMcSeedText] = useState<string>("");
  const mcSeed = mcSeedText.trim() === "" ? null : Number(mcSeedText.trim());
  const seedValid = mcSeed === null || Number.isFinite(mcSeed);

  const { data: mcData, isFetching: mcFetching } = useMonteCarlo(planId, {
    enabled: showMonteCarlo && chart === "net_worth",
    n: mcN,
    seed: seedValid ? mcSeed : null,
  });

  const inflation = assumptions?.inflation_rate ?? 0;
  const baseYear = plan?.base_year ?? data?.years[0]?.year ?? new Date().getFullYear();
  const deflate = useMemo(() => {
    if (!realMode || inflation <= 0) return (_v: number, _year: number) => _v;
    return (v: number, year: number) => v / Math.pow(1 + inflation, year - baseYear);
  }, [realMode, inflation, baseYear]);

  const series = useMemo(() => {
    if (!data) return [];
    return data.years.map((y) => {
      const f = (v: number) => deflate(v, y.year);
      const scaledKindIncomes = Object.fromEntries(
        Object.entries(y.income_by_kind).map(([k, v]) => [k, f(v)]),
      );
      const scaledKindAssets = Object.fromEntries(
        Object.entries(y.asset_balances_by_kind).map(([k, v]) => [k, f(v)]),
      );
      return {
        year: y.year,
        net_worth: f(y.net_worth),
        gross_assets: f(Object.values(y.asset_balances_by_kind).reduce((s, v) => s + v, 0)),
        debt: f(-y.debt_outstanding),
        gross_income: f(y.gross_income_total),
        net_income: f(y.net_income_total),
        expenses: f(y.expenses_total),
        surplus: f(y.surplus_or_shortfall),
        income_tax: f(y.income_tax),
        usc: f(y.usc),
        prsi: f(y.prsi),
        investment_tax: f(y.investment_tax),
        total_tax: f(y.total_tax),
        ...scaledKindIncomes,
        ...scaledKindAssets,
      };
    });
  }, [data, deflate]);

  const mcSeries = useMemo(() => {
    if (!data || !mcData) return series;
    return data.years.map((y, idx) => {
      const mc = mcData.years[idx];
      if (!mc) return { ...series[idx] };
      const f = (v: number) => deflate(v, y.year);
      return {
        ...series[idx],
        mc_p50: f(mc.p50),
        band_base: f(mc.p5),
        band_outer_lo: f(mc.p25 - mc.p5),
        band_inner_lo: f(mc.p50 - mc.p25),
        band_inner_hi: f(mc.p75 - mc.p50),
        band_outer_hi: f(mc.p95 - mc.p75),
      };
    });
  }, [data, mcData, series, deflate]);

  const onToggleReal = () => {
    setRealMode((v) => {
      const next = !v;
      try {
        localStorage.setItem(REAL_TOGGLE_KEY(planId), next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  };
  const onChangeMcN = (n: number) => {
    setMcN(n);
    try {
      localStorage.setItem(MC_N_KEY(planId), String(n));
    } catch {
      /* ignore */
    }
  };

  if (isLoading)
    return (
      <div className="card">
        <ChartSkeleton height={360} />
      </div>
    );
  if (error)
    return <p style={{ color: "#dc2626" }}>Couldn't run projection: {String(error)}</p>;
  if (!data) return null;

  const incomeKinds = Array.from(
    new Set(data.years.flatMap((y) => Object.keys(y.income_by_kind)))
  );

  const defaultYearRow = pickDefaultYear(data.years, people ?? []);
  const hovered: YearRow | undefined = data.years.find((y) => y.year === hoverYear) ?? defaultYearRow;

  return (
    <div>
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <h3 style={{ margin: 0 }}>Let's see</h3>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <button
              className={`btn ${realMode ? "" : "btn-secondary"}`}
              onClick={onToggleReal}
              title={
                realMode
                  ? "Showing in today's euros (inflation-adjusted)."
                  : "Showing in nominal euros (future cash, no inflation adjustment)."
              }
            >
              {realMode ? "Today's € (real)" : "Nominal €"}
            </button>
            {chart === "net_worth" && (
              <button
                className={`btn ${showMonteCarlo ? "" : "btn-secondary"}`}
                onClick={() => setShowMonteCarlo((v) => !v)}
                title={`Run ${mcN} probabilistic simulations and show a fan chart with 5th–95th percentile bands`}
              >
                {mcFetching ? "Running…" : showMonteCarlo ? "Hide bands" : "Probability bands"}
              </button>
            )}
            {chart === "net_worth" && showMonteCarlo && (
              <>
                <select
                  value={mcN}
                  onChange={(e) => onChangeMcN(Number(e.target.value))}
                  style={{ padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: 6 }}
                  title="Number of Monte Carlo runs. More runs = smoother fan, slower compute."
                >
                  <option value={50}>50 runs (fast)</option>
                  <option value={200}>200 runs</option>
                  <option value={1000}>1000 runs (slow)</option>
                </select>
                <details style={{ display: "inline-block" }}>
                  <summary
                    style={{
                      cursor: "pointer",
                      fontSize: 12,
                      color: "#475569",
                      padding: "8px 4px",
                      userSelect: "none",
                    }}
                  >
                    Advanced
                  </summary>
                  <div
                    style={{
                      position: "absolute",
                      background: "#fff",
                      border: "1px solid #cbd5e1",
                      borderRadius: 6,
                      padding: 10,
                      marginTop: 4,
                      zIndex: 5,
                      minWidth: 220,
                    }}
                  >
                    <label
                      style={{ display: "block", fontSize: 12, color: "#475569", marginBottom: 4 }}
                    >
                      RNG seed (optional — for reproducible runs)
                    </label>
                    <input
                      type="text"
                      placeholder="leave blank for random"
                      value={mcSeedText}
                      onChange={(e) => setMcSeedText(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 8px",
                        border: `1px solid ${seedValid ? "#cbd5e1" : "#dc2626"}`,
                        borderRadius: 4,
                        fontSize: 13,
                      }}
                    />
                    {!seedValid && (
                      <p style={{ color: "#dc2626", fontSize: 11, margin: "4px 0 0" }}>
                        Seed must be an integer.
                      </p>
                    )}
                  </div>
                </details>
              </>
            )}
            <select
              value={chart}
              onChange={(e) => {
                setChart(e.target.value as ChartKind);
                if (e.target.value !== "net_worth") setShowMonteCarlo(false);
              }}
              style={{ padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: 6 }}
            >
              {CHART_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <NarrativeSummary
          summary={data.summary}
          finalYear={data.years.at(-1)?.year ?? 0}
          mcData={showMonteCarlo ? mcData : undefined}
          realMode={realMode}
          deflate={deflate}
        />

        <SummaryStrip
          summary={data.summary}
          finalYear={data.years.at(-1)?.year ?? 0}
          mcData={showMonteCarlo ? mcData : undefined}
          realMode={realMode}
          deflate={deflate}
        />

        {goals && goals.length > 0 && (
          <GoalStrip goals={goals} years={data.years} />
        )}

        <div style={{ height: isMobile ? 240 : 380, marginTop: 12 }}>
          <ResponsiveContainer width="100%" height="100%">
            {chart === "net_worth" ? (
              showMonteCarlo && mcData ? (
                <ComposedChart
                  data={mcSeries}
                  onMouseMove={(s: any) => setHoverYear(s?.activeLabel ?? null)}
                  onMouseLeave={() => setHoverYear(null)}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="year" />
                  <YAxis tickFormatter={(v) => compact(v)} />
                  <Tooltip
                    trigger={tooltipTrigger}
                    content={<McTooltip mcData={mcData} deflate={deflate} />}
                    labelFormatter={(l) => `Year ${l}`}
                  />
                  <Legend />
                  {/* Fan band: transparent base offset + stacked delta layers */}
                  <Area type="monotone" dataKey="band_base" stackId="mc"
                    fill="transparent" stroke="none" legendType="none" />
                  <Area type="monotone" dataKey="band_outer_lo" stackId="mc"
                    fill="#bfdbfe" fillOpacity={0.7} stroke="none" name="5–25 / 75–95 %ile" />
                  <Area type="monotone" dataKey="band_inner_lo" stackId="mc"
                    fill="#93c5fd" fillOpacity={0.7} stroke="none" name="25–75 %ile" />
                  <Area type="monotone" dataKey="band_inner_hi" stackId="mc"
                    fill="#93c5fd" fillOpacity={0.7} stroke="none" legendType="none" />
                  <Area type="monotone" dataKey="band_outer_hi" stackId="mc"
                    fill="#bfdbfe" fillOpacity={0.7} stroke="none" legendType="none" />
                  <Line type="monotone" dataKey="mc_p50" stroke="#1d4ed8"
                    strokeWidth={2} dot={false} name="Median (p50)" />
                  <Line type="monotone" dataKey="net_worth" stroke="#64748b"
                    strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="Deterministic" />
                </ComposedChart>
              ) : (
                <AreaChart
                  data={series}
                  onMouseMove={(s: any) => setHoverYear(s?.activeLabel ?? null)}
                  onMouseLeave={() => setHoverYear(null)}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="year" />
                  <YAxis tickFormatter={(v) => compact(v)} />
                  <Tooltip trigger={tooltipTrigger} formatter={(v) => fmtMoney(Number(v))} labelFormatter={(l) => `Year ${l}`} />
                  <Area
                    type="monotone"
                    dataKey="net_worth"
                    stroke="#2563eb"
                    fill="#2563eb"
                    fillOpacity={0.18}
                    name="Net worth"
                  />
                </AreaChart>
              )
            ) : chart === "cash_flow" ? (
              <ComposedChart
                data={series}
                onMouseMove={(s: any) => setHoverYear(s?.activeLabel ?? null)}
                onMouseLeave={() => setHoverYear(null)}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="year" />
                <YAxis tickFormatter={(v) => compact(v)} />
                <Tooltip formatter={(v) => fmtMoney(Number(v))} labelFormatter={(l) => `Year ${l}`} />
                <Legend />
                <Bar dataKey="net_income" fill="#10b981" name="Net income" />
                <Bar dataKey="expenses" fill="#ef4444" name="Expenses" />
                <Line
                  type="monotone"
                  dataKey="surplus"
                  stroke="#0f172a"
                  strokeWidth={2}
                  name="Surplus / shortfall"
                  dot={false}
                />
              </ComposedChart>
            ) : chart === "income_vs_expenses" ? (
              <BarChart
                data={series}
                onMouseMove={(s: any) => setHoverYear(s?.activeLabel ?? null)}
                onMouseLeave={() => setHoverYear(null)}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="year" />
                <YAxis tickFormatter={(v) => compact(v)} />
                <Tooltip formatter={(v) => fmtMoney(Number(v))} labelFormatter={(l) => `Year ${l}`} />
                <Legend />
                {incomeKinds.map((k, i) => (
                  <Bar
                    key={k}
                    dataKey={k}
                    stackId="income"
                    fill={KIND_COLORS[i % KIND_COLORS.length]}
                    name={k.replace(/_/g, " ")}
                  />
                ))}
              </BarChart>
            ) : (
              <BarChart
                data={series}
                onMouseMove={(s: any) => setHoverYear(s?.activeLabel ?? null)}
                onMouseLeave={() => setHoverYear(null)}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="year" />
                <YAxis tickFormatter={(v) => compact(v)} />
                <Tooltip formatter={(v) => fmtMoney(Number(v))} labelFormatter={(l) => `Year ${l}`} />
                <Legend />
                <Bar dataKey="income_tax" stackId="t" fill={TAX_COLORS.income_tax} name="Income tax" />
                <Bar dataKey="usc" stackId="t" fill={TAX_COLORS.usc} name="USC" />
                <Bar dataKey="prsi" stackId="t" fill={TAX_COLORS.prsi} name="PRSI" />
                <Bar dataKey="investment_tax" stackId="t" fill="#f59e0b" name="Investment tax (CGT/ETF)" />
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>

      <YearDetailCard
        row={hovered ?? data.years[0]}
        assets={assets ?? []}
        goals={goals ?? []}
        people={people ?? []}
        deflate={deflate}
        realMode={realMode}
      />
    </div>
  );
}

function pickDefaultYear(years: YearRow[], people: { retirement_age: number | null; dob: string }[]): YearRow | undefined {
  if (years.length === 0) return undefined;
  const shortfall = years.find((y) => y.surplus_or_shortfall < 0);
  if (shortfall) return shortfall;
  const retYears = people
    .filter((p) => p.retirement_age != null)
    .map((p) => new Date(p.dob).getFullYear() + (p.retirement_age as number));
  if (retYears.length > 0) {
    const target = Math.min(...retYears);
    const hit = years.find((y) => y.year >= target);
    if (hit) return hit;
  }
  return years[0];
}

function GoalStrip({ goals, years }: { goals: Goal[]; years: YearRow[] }) {
  return (
    <div
      className="row"
      style={{
        marginTop: 12,
        paddingTop: 12,
        borderTop: "1px solid #e2e8f0",
        gap: 8,
        flexWrap: "wrap",
      }}
    >
      <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.04, width: "100%" }}>
        Goal status
      </div>
      {goals.map((g) => {
        const targetRow = years.find((y) => y.year === g.target_year);
        const status = targetRow?.goal_status?.[g.id] ?? "pending";
        const meta = goalStatusMeta(status);
        return (
          <span
            key={g.id}
            title={`${g.name} — target ${g.target_year}`}
            style={{
              display: "inline-flex",
              gap: 6,
              alignItems: "center",
              padding: "4px 10px",
              borderRadius: 999,
              background: meta.bg,
              color: meta.fg,
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            <span>{meta.icon}</span>
            <span>{g.name}</span>
            <span style={{ opacity: 0.7, fontWeight: 400 }}>· {g.target_year}</span>
          </span>
        );
      })}
    </div>
  );
}

function goalStatusMeta(status: string): { icon: string; bg: string; fg: string } {
  switch (status) {
    case "achieved":
    case "met":
      return { icon: "✅", bg: "#dcfce7", fg: "#166534" };
    case "missed":
    case "below_target":
      return { icon: "⚠", bg: "#fee2e2", fg: "#991b1b" };
    default:
      return { icon: "⏳", bg: "#e2e8f0", fg: "#475569" };
  }
}

function NarrativeSummary({
  summary,
  finalYear,
  mcData,
  realMode,
  deflate,
}: {
  summary: {
    final_net_worth: number;
    peak_net_worth: number;
    peak_net_worth_year: number;
    first_shortfall_year: number | null;
    total_lifetime_tax: number;
  };
  finalYear: number;
  mcData?: MonteCarloResponse;
  realMode: boolean;
  deflate: (v: number, year: number) => number;
}) {
  const shortfallYear = summary.first_shortfall_year;
  const stayedFunded = shortfallYear == null;
  const peakStr = fmtMoney(deflate(summary.peak_net_worth, summary.peak_net_worth_year));
  const finalStr = fmtMoney(deflate(summary.final_net_worth, finalYear));
  const suffix = realMode ? " (today's €)" : "";

  let headline: string;
  let tone: "good" | "warn" | "bad";
  if (stayedFunded) {
    headline = `On track. Your plan stays funded all the way to ${finalYear}.`;
    tone = "good";
  } else {
    headline = `Funds run short in ${shortfallYear}. Without changes, your assets exhaust that year.`;
    tone = "bad";
  }

  let mcSentence: string | null = null;
  if (mcData) {
    const pct = mcData.shortfall_probability * 100;
    if (pct < 5) {
      mcSentence = `Across ${mcData.runs} probabilistic runs, fewer than 5% end in shortfall — a robust plan.`;
      if (tone === "good") tone = "good";
    } else if (pct < 20) {
      mcSentence = `Across ${mcData.runs} probabilistic runs, ${pct.toFixed(0)}% end in shortfall — some room to tighten.`;
      if (tone === "good") tone = "warn";
    } else {
      mcSentence = `Across ${mcData.runs} probabilistic runs, ${pct.toFixed(0)}% end in shortfall — your plan is sensitive to market downturns.`;
      tone = "bad";
    }
  }

  const peakSentence =
    summary.peak_net_worth_year === finalYear
      ? `Net worth grows throughout, peaking at ${finalStr} in ${finalYear}${suffix}.`
      : `Peak net worth: ${peakStr} in ${summary.peak_net_worth_year}; final net worth ${finalStr} at ${finalYear}${suffix}.`;

  const colors = {
    good: { bg: "#ecfdf5", border: "#10b981", icon: "✅" },
    warn: { bg: "#fef3c7", border: "#f59e0b", icon: "⚠" },
    bad: { bg: "#fef2f2", border: "#dc2626", icon: "⚠" },
  }[tone];

  return (
    <div
      style={{
        background: colors.bg,
        borderLeft: `4px solid ${colors.border}`,
        padding: "10px 14px",
        borderRadius: 6,
        marginTop: 12,
        fontSize: 14,
        lineHeight: 1.5,
      }}
    >
      <strong>{colors.icon} {headline}</strong>
      <div style={{ color: "#334155", marginTop: 2 }}>
        {peakSentence}
        {mcSentence ? ` ${mcSentence}` : null}
      </div>
    </div>
  );
}

function SummaryStrip({
  summary,
  finalYear,
  mcData,
  realMode,
  deflate,
}: {
  summary: ReturnType<typeof Object.assign> & {
    final_net_worth: number;
    peak_net_worth: number;
    peak_net_worth_year: number;
    first_shortfall_year: number | null;
    total_lifetime_tax: number;
  };
  finalYear: number;
  mcData?: MonteCarloResponse;
  realMode: boolean;
  deflate: (v: number, year: number) => number;
}) {
  const suffix = realMode ? " (today's €)" : "";
  return (
    <div
      className="row"
      style={{
        marginTop: 12,
        paddingTop: 12,
        borderTop: "1px solid #e2e8f0",
        gap: 32,
        flexWrap: "wrap",
      }}
    >
      <Stat
        label={`Net worth ${finalYear}${suffix}`}
        value={fmtMoney(deflate(summary.final_net_worth, finalYear))}
      />
      {summary.peak_net_worth_year !== finalYear && (
        <Stat
          label={`Peak net worth${suffix}`}
          value={fmtMoney(deflate(summary.peak_net_worth, summary.peak_net_worth_year))}
          sub={`in ${summary.peak_net_worth_year}`}
        />
      )}
      <Stat
        label={`Lifetime tax${realMode ? " (nominal €)" : ""}`}
        value={fmtMoney(summary.total_lifetime_tax)}
      />
      <Stat
        label="First shortfall"
        value={summary.first_shortfall_year ? String(summary.first_shortfall_year) : "—"}
        sub={summary.first_shortfall_year ? "year assets exhaust" : "plan stays funded"}
      />
      {mcData && (
        <Stat
          label="Shortfall probability"
          value={`${(mcData.shortfall_probability * 100).toFixed(1)}% ${shortfallMoE(mcData.shortfall_probability, mcData.runs)}`}
          sub={`chance of running short · ${mcData.runs} runs · 95% CI`}
        />
      )}
    </div>
  );
}

function shortfallMoE(p: number, n: number): string {
  if (n <= 0) return "";
  const moe = 1.96 * Math.sqrt(Math.max(0, p * (1 - p)) / n);
  const moePct = moe * 100;
  if (moePct < 0.05) return "";
  return `±${moePct.toFixed(moePct < 1 ? 2 : 1)}%`;
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.04 }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 600 }}>{value}</div>
      {sub && (
        <div className="muted" style={{ fontSize: 12 }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function YearDetailCard({
  row,
  assets,
  goals,
  people,
  deflate,
  realMode,
}: {
  row?: YearRow;
  assets: { id: number; name: string }[];
  goals: Goal[];
  people: { id: number; name: string }[];
  deflate: (v: number, year: number) => number;
  realMode: boolean;
}) {
  if (!row) return null;
  const tax = row.total_tax;
  const taxRate = row.gross_income_total > 0 ? tax / row.gross_income_total : 0;
  const fy = (v: number) => fmtMoney(deflate(v, row.year));
  const withdrawals = Object.entries(row.withdrawals_by_asset ?? {})
    .map(([id, v]) => ({ id: Number(id), amount: v }))
    .filter((w) => w.amount > 0);
  const yearGoals = goals.filter((g) => row.goal_status?.[g.id]);
  const estateRows = Object.entries(row.estate_transfers ?? {})
    .map(([pid, amt]) => ({ pid: Number(pid), amount: amt }))
    .filter((e) => e.amount > 0);
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>
        Year {row.year}
        {realMode && (
          <span className="muted" style={{ fontSize: 12, fontWeight: 400, marginLeft: 8 }}>
            (today's €)
          </span>
        )}
      </h3>
      <div className="row" style={{ gap: 32, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h4 style={{ margin: "0 0 6px 0", color: "#475569", fontSize: 13 }}>Income</h4>
          <Row label="Gross income" value={fy(row.gross_income_total)} />
          <Row label="Income tax" value={fy(row.income_tax)} />
          <Row label={<JargonTerm term="USC" />} value={fy(row.usc)} />
          <Row label={<JargonTerm term="PRSI" />} value={fy(row.prsi)} />
          <Row
            label="Effective tax rate"
            value={`${(taxRate * 100).toFixed(1)}%`}
            muted
          />
          {row.state_pension_total > 0 && (
            <Row
              label={<JargonTerm term="STATE_PENSION">State pension</JargonTerm>}
              value={fy(row.state_pension_total)}
              muted
            />
          )}
          {row.arf_drawdowns > 0 && (
            <Row
              label={<JargonTerm term="ARF">ARF drawdown</JargonTerm>}
              value={fy(row.arf_drawdowns)}
              muted
            />
          )}
          {row.pension_contributions > 0 && (
            <Row
              label="Pension contribution"
              value={`-${fy(row.pension_contributions)}`}
              muted
            />
          )}
          {row.asset_contributions > 0 && (
            <Row
              label="Regular investing"
              value={`-${fy(row.asset_contributions)}`}
              muted
            />
          )}
          <Row label="Net income" value={fy(row.net_income_total)} bold />
          {row.pension_lump_sum > 0 && (
            <Row
              label={<JargonTerm term="LUMP_SUM">Retirement lump sum</JargonTerm>}
              value={fy(row.pension_lump_sum)}
              color="#10b981"
            />
          )}
          {row.pension_lump_sum_tax > 0 && (
            <Row
              label="Lump-sum tax"
              value={fy(row.pension_lump_sum_tax)}
              muted
            />
          )}
        </div>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h4 style={{ margin: "0 0 6px 0", color: "#475569", fontSize: 13 }}>Expenses</h4>
          {Object.entries(row.expenses_by_category).map(([cat, amt]) => (
            <Row key={cat} label={cat.replace(/_/g, " ")} value={fy(amt)} />
          ))}
          <Row label="Total" value={fy(row.expenses_total)} bold />
          <Row
            label="Surplus / shortfall"
            value={fy(row.surplus_or_shortfall)}
            bold
            color={row.surplus_or_shortfall < 0 ? "#dc2626" : "#10b981"}
          />
          {withdrawals.length > 0 && (
            <>
              <h4 style={{ margin: "10px 0 4px 0", color: "#475569", fontSize: 13 }}>
                Withdrawals to cover shortfall
              </h4>
              {withdrawals.map((w) => {
                const asset = assets.find((a) => a.id === w.id);
                const name = asset?.name ?? syntheticAssetName(w.id);
                return <Row key={w.id} label={name} value={fy(w.amount)} muted />;
              })}
            </>
          )}
        </div>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h4 style={{ margin: "0 0 6px 0", color: "#475569", fontSize: 13 }}>Assets</h4>
          {Object.entries(row.asset_balances_by_kind).map(([kind, bal]) => (
            <Row key={kind} label={kind.replace(/_/g, " ")} value={fy(bal)} />
          ))}
          {row.debt_outstanding > 0 && (
            <Row label="Debt" value={`-${fy(row.debt_outstanding)}`} color="#dc2626" />
          )}
          {row.investment_tax > 0 && (
            <Row
              label={<JargonTerm term="CGT">Investment tax (CGT / ETF)</JargonTerm>}
              value={fy(row.investment_tax)}
              muted
            />
          )}
          <Row label="Net worth" value={fy(row.net_worth)} bold />
          {row.accessible_net_worth < row.net_worth - 1 && (
            <Row
              label="Accessible (ex-locked pensions)"
              value={fy(row.accessible_net_worth)}
              muted
            />
          )}
          {estateRows.length > 0 && (
            <>
              <h4 style={{ margin: "10px 0 4px 0", color: "#475569", fontSize: 13 }}>
                Estate transfers
              </h4>
              {estateRows.map((e) => {
                const name = people.find((p) => p.id === e.pid)?.name ?? `Person ${e.pid}`;
                return <Row key={e.pid} label={`${name} estate`} value={fy(e.amount)} muted />;
              })}
              {row.cat_paid > 0 && (
                <Row
                  label={<JargonTerm term="CAT">CAT paid</JargonTerm>}
                  value={fy(row.cat_paid)}
                  muted
                />
              )}
            </>
          )}
          {yearGoals.length > 0 && (
            <>
              <h4 style={{ margin: "10px 0 4px 0", color: "#475569", fontSize: 13 }}>
                Goals
              </h4>
              {yearGoals.map((g) => {
                const m = goalStatusMeta(row.goal_status?.[g.id] ?? "pending");
                return (
                  <Row
                    key={g.id}
                    label={`${m.icon} ${g.name}`}
                    value={(row.goal_status?.[g.id] ?? "pending").replace(/_/g, " ")}
                    color={m.fg}
                  />
                );
              })}
            </>
          )}
        </div>
      </div>
      {row.notes.length > 0 && (
        <div style={{ marginTop: 12 }}>
          {row.notes.map((n, i) => (
            <p key={i} style={{ color: "#dc2626", fontSize: 13, margin: "4px 0" }}>
              ⚠ {n}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// Cell is imported but only used inside specific charts conditionally; keep import to avoid unused warning.
void Cell;

function syntheticAssetName(id: number): string {
  if (id === -1) return "Cash";
  if (id <= -2000) return `ARF (person ${-(id + 2000)})`;
  if (id <= -1000) return `Pension wrapper (person ${-(id + 1000)})`;
  return `Asset ${id}`;
}

function Row({
  label,
  value,
  bold,
  muted,
  color,
}: {
  label: React.ReactNode;
  value: string;
  bold?: boolean;
  muted?: boolean;
  color?: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        padding: "3px 0",
        fontSize: 14,
        color: color ?? (muted ? "#64748b" : "inherit"),
        fontWeight: bold ? 600 : 400,
        borderTop: bold ? "1px solid #e2e8f0" : undefined,
        marginTop: bold ? 4 : 0,
        paddingTop: bold ? 6 : 3,
      }}
    >
      <span style={{ textTransform: "capitalize" }}>{label}</span>
      <span>{value}</span>
    </div>
  );
}

function McTooltip({ active, payload, label, mcData, deflate }: {
  active?: boolean;
  payload?: any[];
  label?: number;
  mcData: MonteCarloResponse;
  deflate: (v: number, year: number) => number;
}) {
  if (!active || !label) return null;
  const mc = mcData.years.find((y) => y.year === label);
  const det = payload?.find((p) => p.dataKey === "net_worth")?.value;
  if (!mc) return null;
  const d = (v: number) => fmtMoney(deflate(v, label));
  return (
    <div style={{
      background: "white", border: "1px solid #e2e8f0", borderRadius: 6,
      padding: "8px 12px", fontSize: 13, minWidth: 200,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Year {label}</div>
      <div style={{ color: "#64748b" }}>Deterministic: {fmtMoney(det ?? 0)}</div>
      <div style={{ color: "#1d4ed8" }}>Median (p50): {d(mc.p50)}</div>
      <div style={{ color: "#93c5fd" }}>Range p25–p75: {d(mc.p25)} – {d(mc.p75)}</div>
      <div style={{ color: "#bfdbfe" }}>Range p5–p95: {d(mc.p5)} – {d(mc.p95)}</div>
    </div>
  );
}

function compact(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `€${(n / 1_000).toFixed(0)}k`;
  return `€${n.toFixed(0)}`;
}
