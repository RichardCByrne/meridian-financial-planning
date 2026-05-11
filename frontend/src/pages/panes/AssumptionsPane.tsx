import { useEffect, useState } from "react";

import { useAssumptions, useUpsertAssumptions } from "../../api/hooks";
import type { AssumptionsUpsert } from "../../api/types";
import { HelpTip } from "../../components/HelpTip";
import { NumericInput } from "../../components/NumericInput";

const DEFAULTS: AssumptionsUpsert = {
  inflation_rate: 0.025,
  default_growth_rate: 0.05,
  property_growth_rate: 0.03,
  earnings_growth: 0.03,
  state_pension_age: 66,
  state_pension_annual_amount: 15_563,
  state_pension_escalation_rate: 0.015,
};

export function AssumptionsPane({ planId }: { planId: number }) {
  const { data, isLoading } = useAssumptions(planId);
  const save = useUpsertAssumptions(planId);
  const [form, setForm] = useState<AssumptionsUpsert>(DEFAULTS);

  useEffect(() => {
    if (data) {
      setForm({
        inflation_rate: data.inflation_rate,
        default_growth_rate: data.default_growth_rate,
        property_growth_rate: data.property_growth_rate,
        earnings_growth: data.earnings_growth,
        state_pension_age: data.state_pension_age,
        state_pension_annual_amount: data.state_pension_annual_amount,
        state_pension_escalation_rate: data.state_pension_escalation_rate ?? 0.015,
      });
    }
  }, [data]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await save.mutateAsync(form);
  };

  if (isLoading) return <p className="muted">Loading…</p>;

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <h3 style={{ marginTop: 0 }}>Plan assumptions</h3>
      <p className="muted">
        Defaults applied to all simulation years. Override per asset/income later.
      </p>
      <form onSubmit={onSubmit}>
        <PercentField
          label="Inflation rate"
          value={form.inflation_rate}
          onChange={(v) => setForm({ ...form, inflation_rate: v })}
        />
        <PercentField
          label="Default investment growth"
          value={form.default_growth_rate}
          onChange={(v) => setForm({ ...form, default_growth_rate: v })}
        />
        <PercentField
          label="Property growth"
          value={form.property_growth_rate}
          onChange={(v) => setForm({ ...form, property_growth_rate: v })}
        />
        <PercentField
          label="Earnings growth"
          value={form.earnings_growth}
          onChange={(v) => setForm({ ...form, earnings_growth: v })}
        />
        <div className="field">
          <label>
            State pension age
            <HelpTip>
              Age at which the Irish State Pension (Contributory) begins (currently 66).
            </HelpTip>
          </label>
          <NumericInput
            integer
            value={form.state_pension_age}
            onChange={(v) => Number.isFinite(v) && setForm({ ...form, state_pension_age: v })}
          />
        </div>
        <div className="field">
          <label>
            State pension <span className="muted" style={{ textTransform: "none" }}>(€ per year, today's value)</span>
          </label>
          <NumericInput
            value={form.state_pension_annual_amount}
            onChange={(v) => Number.isFinite(v) && setForm({ ...form, state_pension_annual_amount: v })}
          />
        </div>
        <PercentField
          label="State pension growth rate"
          value={form.state_pension_escalation_rate}
          onChange={(v) => setForm({ ...form, state_pension_escalation_rate: v })}
          help="How fast the state pension rises each year. Historical CAGR 2007–2026: ~1.9% nominal — well below general inflation due to multi-year freezes (2009–15, 2019–21). Default 1.5% is deliberately conservative."
        />
        <div className="row" style={{ gap: 8, marginTop: 4 }}>
          <button type="submit" className="btn" disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save assumptions"}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setForm(DEFAULTS)}
            disabled={save.isPending}
            title="Reset all fields to Ireland 2026 defaults (does not save until you click Save)"
          >
            Reset to Ireland 2026 defaults
          </button>
        </div>
      </form>
    </div>
  );
}

function PercentField({
  label,
  value,
  onChange,
  help,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  help?: string;
}) {
  return (
    <div className="field">
      <label>
        {label} <span className="muted" style={{ textTransform: "none" }}>(% per year)</span>
        {help && <HelpTip>{help}</HelpTip>}
      </label>
      <NumericInput
        value={value * 100}
        onChange={(v) => Number.isFinite(v) && onChange(v / 100)}
      />
    </div>
  );
}
