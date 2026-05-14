import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useCompare, useScenarios } from "../../api/hooks";
import { fmtMoney } from "../../lib/format";
import { useIsMobile } from "../../hooks/useIsMobile";

const COLOR_A = "#2563eb";
const COLOR_B = "#7c3aed";
const COLOR_DELTA_POS = "#10b981";
const COLOR_DELTA_NEG = "#ef4444";

export function ComparePane({ planId }: { planId: number }) {
  const { data: scenarios } = useScenarios(planId);
  const [a, setA] = useState<number | null>(null); // null = base
  const [b, setB] = useState<number | null>(null);
  const { data, isLoading, error } = useCompare(planId, a, b);
  const [focusKey, setFocusKey] = useState<string | null>(null);
  const [stickyFocus, setStickyFocus] = useState<string | null>(null);
  const isMobile = useIsMobile();
  const tooltipTrigger = isMobile ? "click" : "hover";
  const activeFocus = stickyFocus ?? focusKey;

  const opacityFor = (key: string) => (activeFocus && activeFocus !== key ? 0.2 : 1);
  const widthFor = (key: string) => (activeFocus === key ? 3 : 1.5);

  const legendKey = (o: { dataKey?: unknown }): string | null =>
    typeof o.dataKey === "string" ? o.dataKey : null;
  const onLegendClick = (o: { dataKey?: unknown }) => {
    const k = legendKey(o);
    setStickyFocus((prev) => (prev === k ? null : k));
  };
  const onLegendPointerEnter = (o: { dataKey?: unknown }) => {
    setFocusKey(legendKey(o));
  };
  const onLegendPointerLeave = () => setFocusKey(null);

  const series = useMemo(() => {
    if (!data) return [];
    // Scenarios A and B may diverge in horizon length if one is shorter; only
    // chart the overlapping prefix so we never dereference a missing year.
    const overlap = Math.min(
      data.a.projection.years.length,
      data.b.projection.years.length,
      data.delta.length,
    );
    const out = [];
    for (let i = 0; i < overlap; i++) {
      const ya = data.a.projection.years[i];
      const yb = data.b.projection.years[i];
      const d = data.delta[i];
      out.push({
        year: ya.year,
        a_net_worth: ya.net_worth,
        b_net_worth: yb.net_worth,
        a_expenses: ya.expenses_total,
        b_expenses: yb.expenses_total,
        a_tax: ya.total_tax + ya.investment_tax,
        b_tax: yb.total_tax + yb.investment_tax,
        net_worth_delta: d.net_worth_delta,
      });
    }
    return out;
  }, [data]);

  const finalDelta = data?.delta[data.delta.length - 1];
  const finalYear = data?.delta[data.delta.length - 1]?.year;
  const headline = useMemo(() => {
    if (!data || !finalDelta) return null;
    const delta = finalDelta.net_worth_delta;
    const aName = data.a.scenario_name;
    const bName = data.b.scenario_name;
    if (Math.abs(delta) < 1) {
      return `${bName} and ${aName} end at roughly the same net worth in ${finalYear}.`;
    }
    const winner = delta > 0 ? bName : aName;
    const loser = delta > 0 ? aName : bName;
    return `${winner} ends €${Math.abs(delta).toLocaleString(undefined, { maximumFractionDigits: 0 })} ahead of ${loser} by ${finalYear}.`;
  }, [data, finalDelta, finalYear]);

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Compare scenarios</h3>
        {headline && (
          <div
            style={{
              background: finalDelta && finalDelta.net_worth_delta >= 0 ? "#ecfdf5" : "#fef2f2",
              borderLeft: `4px solid ${finalDelta && finalDelta.net_worth_delta >= 0 ? COLOR_DELTA_POS : COLOR_DELTA_NEG}`,
              padding: "10px 14px",
              borderRadius: 6,
              marginBottom: 12,
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            {headline}
          </div>
        )}
        <div className="row" style={{ flexWrap: "wrap", gap: 24 }}>
          <ScenarioPicker
            label="Series A"
            color={COLOR_A}
            value={a}
            onChange={setA}
            scenarios={scenarios ?? []}
          />
          <ScenarioPicker
            label="Series B"
            color={COLOR_B}
            value={b}
            onChange={setB}
            scenarios={scenarios ?? []}
          />
          {finalDelta && (
            <div style={{ marginLeft: "auto" }}>
              <div className="muted" style={{ fontSize: 11, textTransform: "uppercase" }}>
                Final-year net-worth delta (B − A)
              </div>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: finalDelta.net_worth_delta >= 0 ? COLOR_DELTA_POS : COLOR_DELTA_NEG,
                }}
              >
                {finalDelta.net_worth_delta >= 0 ? "+" : ""}
                {fmtMoney(finalDelta.net_worth_delta)}
              </div>
            </div>
          )}
        </div>
      </div>

      {isLoading && <p className="muted">Loading…</p>}
      {error && <p style={{ color: "#dc2626" }}>Failed to load comparison.</p>}

      {data && series.length > 0 && (
        <>
          <div className="card">
            <h4 style={{ marginTop: 0 }}>Net worth</h4>
            <ResponsiveContainer width="100%" height={isMobile ? 220 : 300}>
              <LineChart data={series} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => fmtMoney(Number(v))} />
                <Tooltip trigger={tooltipTrigger} formatter={(v) => fmtMoney(Number(v))} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="a_net_worth"
                  stroke={COLOR_A}
                  strokeWidth={2}
                  dot={false}
                  name={data.a.scenario_name}
                />
                <Line
                  type="monotone"
                  dataKey="b_net_worth"
                  stroke={COLOR_B}
                  strokeWidth={2}
                  dot={false}
                  name={data.b.scenario_name}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h4 style={{ marginTop: 0 }}>Net-worth delta (B − A)</h4>
            <ResponsiveContainer width="100%" height={isMobile ? 110 : 140}>
              <BarChart data={series} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => fmtMoney(Number(v))} />
                <Tooltip trigger={tooltipTrigger} formatter={(v) => fmtMoney(Number(v))} />
                <ReferenceLine y={0} stroke="#94a3b8" />
                <Bar dataKey="net_worth_delta" name="Delta">
                  {series.map((s) => (
                    <Cell
                      key={s.year}
                      fill={s.net_worth_delta >= 0 ? COLOR_DELTA_POS : COLOR_DELTA_NEG}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h4 style={{ marginTop: 0 }}>Expenses & tax over time</h4>
            <p className="muted" style={{ marginTop: 0, fontSize: 12 }}>
              Dotted lines = expenses. Solid lines = total tax (income + investment). Tap (or
              hover) a legend entry to focus its line; tap again to clear.
            </p>
            <ResponsiveContainer width="100%" height={isMobile ? 200 : 260}>
              <LineChart data={series} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => fmtMoney(Number(v))} />
                <Tooltip trigger={tooltipTrigger} formatter={(v) => fmtMoney(Number(v))} />
                <Legend
                  onClick={onLegendClick}
                  onPointerEnter={onLegendPointerEnter}
                  onPointerLeave={onLegendPointerLeave}
                />
                <Line
                  type="monotone"
                  dataKey="a_expenses"
                  stroke={COLOR_A}
                  strokeDasharray="4 4"
                  strokeOpacity={opacityFor("a_expenses")}
                  strokeWidth={widthFor("a_expenses")}
                  dot={false}
                  name={`${data.a.scenario_name} · expenses`}
                />
                <Line
                  type="monotone"
                  dataKey="b_expenses"
                  stroke={COLOR_B}
                  strokeDasharray="4 4"
                  strokeOpacity={opacityFor("b_expenses")}
                  strokeWidth={widthFor("b_expenses")}
                  dot={false}
                  name={`${data.b.scenario_name} · expenses`}
                />
                <Line
                  type="monotone"
                  dataKey="a_tax"
                  stroke={COLOR_A}
                  strokeOpacity={opacityFor("a_tax")}
                  strokeWidth={widthFor("a_tax")}
                  dot={false}
                  name={`${data.a.scenario_name} · tax`}
                />
                <Line
                  type="monotone"
                  dataKey="b_tax"
                  stroke={COLOR_B}
                  strokeOpacity={opacityFor("b_tax")}
                  strokeWidth={widthFor("b_tax")}
                  dot={false}
                  name={`${data.b.scenario_name} · tax`}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h4 style={{ marginTop: 0 }}>Summary</h4>
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th style={{ color: COLOR_A }}>{data.a.scenario_name}</th>
                  <th style={{ color: COLOR_B }}>{data.b.scenario_name}</th>
                  <th>Delta (B − A)</th>
                </tr>
              </thead>
              <tbody>
                <SummaryRow
                  label="Final net worth"
                  a={data.a.projection.summary.final_net_worth}
                  b={data.b.projection.summary.final_net_worth}
                />
                <SummaryRow
                  label="Peak net worth"
                  a={data.a.projection.summary.peak_net_worth}
                  b={data.b.projection.summary.peak_net_worth}
                />
                <SummaryRow
                  label="Lifetime tax"
                  a={data.a.projection.summary.total_lifetime_tax}
                  b={data.b.projection.summary.total_lifetime_tax}
                />
                <tr>
                  <td>First shortfall year</td>
                  <td>{data.a.projection.summary.first_shortfall_year ?? "—"}</td>
                  <td>{data.b.projection.summary.first_shortfall_year ?? "—"}</td>
                  <td className="muted">—</td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function SummaryRow({ label, a, b }: { label: string; a: number; b: number }) {
  const delta = b - a;
  return (
    <tr>
      <td>{label}</td>
      <td>{fmtMoney(a)}</td>
      <td>{fmtMoney(b)}</td>
      <td style={{ color: delta >= 0 ? COLOR_DELTA_POS : COLOR_DELTA_NEG, fontWeight: 600 }}>
        {delta >= 0 ? "+" : ""}
        {fmtMoney(delta)}
      </td>
    </tr>
  );
}

function ScenarioPicker({
  label,
  color,
  value,
  onChange,
  scenarios,
}: {
  label: string;
  color: string;
  value: number | null;
  onChange: (v: number | null) => void;
  scenarios: { id: number; name: string }[];
}) {
  return (
    <div className="field" style={{ marginBottom: 0 }}>
      <label style={{ color }}>{label}</label>
      <select
        value={value === null ? "" : value}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
      >
        <option value="">Base plan</option>
        {scenarios.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </div>
  );
}
