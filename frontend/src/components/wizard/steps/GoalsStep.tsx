import { useState, type ReactNode } from "react";

import type { GoalKind } from "../../../api/types";
import { useWizard, type GoalDraft } from "../../../wizard/store";
import { HelpTip } from "../../HelpTip";
import { NumericInput } from "../../NumericInput";
import { ResponsiveSelect } from "../../ResponsiveSelect";

interface KindMeta {
  value: GoalKind;
  label: string;
  description?: string;
  amountLabel: string;
  amountHelp: ReactNode;
}

const KINDS: KindMeta[] = [
  {
    value: "retirement",
    label: "Retirement nest egg",
    description: "Accessible wealth target at the retirement year",
    amountLabel: "Nest egg target (€)",
    amountHelp: (
      <>
        Lump sum of liquid wealth (everything except your own pre-retirement pension wrappers) you
        want to have by the target year. A common rule of thumb: <strong>25× your desired annual
        retirement spend</strong> (the "4% rule"). Use the estimator below if you'd prefer to think
        in annual spend.
      </>
    ),
  },
  {
    value: "pre_retirement_spend",
    label: "Pre-retirement spend",
    amountLabel: "Amount to spend (€)",
    amountHelp: <>One-off spend in the target year. Added to that year's expenses.</>,
  },
  {
    value: "milestone",
    label: "Milestone",
    description: "One-off event (car, wedding, etc.)",
    amountLabel: "Cost (€)",
    amountHelp: <>One-off cost in the target year. Added to that year's expenses.</>,
  },
  {
    value: "education",
    label: "Education",
    amountLabel: "Cost (€)",
    amountHelp: (
      <>
        Lump-sum cost in the target year (e.g. tuition). For recurring fees, add expenses
        separately.
      </>
    ),
  },
  {
    value: "net_worth",
    label: "Net worth target",
    amountLabel: "Net worth target (€)",
    amountHelp: (
      <>
        Total accessible net worth you want to reach by the target year. Pre-retirement pension
        wrappers don't count toward this.
      </>
    ),
  },
  {
    value: "gift",
    label: "Gift / inheritance",
    amountLabel: "Amount (€)",
    amountHelp: <>One-off transfer out in the target year. Added to that year's expenses.</>,
  },
];

const KIND_BY_VALUE: Record<GoalKind, KindMeta> = Object.fromEntries(
  KINDS.map((k) => [k.value, k]),
) as Record<GoalKind, KindMeta>;

export function GoalsStep() {
  const goals = useWizard((s) => s.goals);
  const people = useWizard((s) => s.people);
  const plan = useWizard((s) => s.plan);
  const addGoal = useWizard((s) => s.addGoal);
  const updateGoal = useWizard((s) => s.updateGoal);
  const removeGoal = useWizard((s) => s.removeGoal);

  const baseYear = plan.base_year ?? new Date().getFullYear();

  const onAdd = () =>
    addGoal({
      kind: "retirement",
      name: "",
      target_amount: 0,
      target_year: baseYear + 20,
      linked_person_id: null,
      linkedPersonDraftId: people[0]?.draftId ?? null,
      notes: null,
    });

  const personOptions: { value: string; label: string }[] = [
    { value: "", label: "(no linked person)" },
    ...people.map((p) => ({ value: p.draftId, label: p.name || "Unnamed" })),
  ];

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {goals.length === 0 && (
        <div className="muted" style={{ color: "#64748b" }}>
          Add goals you want the projection to grade — e.g. "retire at 65 with €1M nest egg".
        </div>
      )}
      {goals.map((g) => (
        <GoalRow
          key={g.draftId}
          goal={g}
          personOptions={personOptions}
          onChange={(patch) => updateGoal(g.draftId, patch)}
          onRemove={() => removeGoal(g.draftId)}
        />
      ))}
      <button
        type="button"
        className="btn btn-secondary"
        onClick={onAdd}
        style={{ minHeight: 44 }}
      >
        + Add goal
      </button>
    </div>
  );
}

function GoalRow({
  goal,
  personOptions,
  onChange,
  onRemove,
}: {
  goal: GoalDraft;
  personOptions: { value: string; label: string }[];
  onChange: (patch: Partial<GoalDraft>) => void;
  onRemove: () => void;
}) {
  const meta = KIND_BY_VALUE[goal.kind];
  return (
    <div className="card" style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Name</span>
          <input
            value={goal.name}
            onChange={(e) => onChange({ name: e.target.value })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Kind</span>
          <ResponsiveSelect<GoalKind>
            value={goal.kind}
            onChange={(v) => onChange({ kind: v })}
            options={KINDS.map((k) => ({
              value: k.value,
              label: k.label,
              description: k.description,
            }))}
            label="Goal kind"
          />
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 }}>
            {meta.amountLabel}
            <HelpTip>{meta.amountHelp}</HelpTip>
          </span>
          <NumericInput
            value={goal.target_amount}
            onChange={(v) => onChange({ target_amount: Number.isFinite(v) ? v : 0 })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Target year</span>
          <NumericInput
            integer
            value={goal.target_year}
            onChange={(v) =>
              onChange({ target_year: Number.isFinite(v) ? v : goal.target_year })
            }
            style={inputStyle}
          />
        </label>
      </div>
      {goal.kind === "retirement" && (
        <RetirementEstimator
          onApply={(amount) => onChange({ target_amount: amount })}
        />
      )}
      <label style={{ display: "grid", gap: 4 }}>
        <span style={{ fontWeight: 600 }}>Linked person (optional)</span>
        <ResponsiveSelect<string>
          value={goal.linkedPersonDraftId ?? ""}
          onChange={(v) => onChange({ linkedPersonDraftId: v === "" ? null : v })}
          options={personOptions}
          label="Linked person"
        />
      </label>
      <button
        type="button"
        className="btn btn-secondary"
        onClick={onRemove}
        style={{ minHeight: 44, alignSelf: "flex-start" }}
      >
        Remove
      </button>
    </div>
  );
}

function RetirementEstimator({ onApply }: { onApply: (amount: number) => void }) {
  const [annualSpend, setAnnualSpend] = useState<number>(40000);
  const [withdrawalPct, setWithdrawalPct] = useState<number>(4);
  const target =
    withdrawalPct > 0 && Number.isFinite(annualSpend)
      ? Math.round(annualSpend / (withdrawalPct / 100))
      : 0;
  return (
    <div
      style={{
        background: "#f8fafc",
        border: "1px dashed #cbd5e1",
        borderRadius: 6,
        padding: 12,
        display: "grid",
        gap: 8,
      }}
    >
      <div style={{ fontWeight: 600, fontSize: 13, color: "#334155" }}>
        Estimate from annual spend
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontSize: 13, color: "#475569" }}>Desired annual spend (€)</span>
          <NumericInput
            value={annualSpend}
            onChange={(v) => setAnnualSpend(Number.isFinite(v) ? v : 0)}
            style={smallInput}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontSize: 13, color: "#475569" }}>Safe withdrawal rate (%)</span>
          <NumericInput
            value={withdrawalPct}
            onChange={(v) => setWithdrawalPct(Number.isFinite(v) && v > 0 ? v : 4)}
            style={smallInput}
          />
        </label>
      </div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 13, color: "#334155" }}>
          Suggested nest egg: <strong>€{target.toLocaleString()}</strong>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => onApply(target)}
          style={{ minHeight: 36 }}
        >
          Use this
        </button>
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "10px 12px",
  border: "1px solid #cbd5e1",
  borderRadius: 6,
  fontSize: 16,
  minHeight: 44,
};

const smallInput: React.CSSProperties = {
  padding: "8px 10px",
  border: "1px solid #cbd5e1",
  borderRadius: 6,
  fontSize: 15,
  minHeight: 40,
};
