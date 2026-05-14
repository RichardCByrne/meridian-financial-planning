import type { GoalKind } from "../../../api/types";
import { useWizard, type GoalDraft } from "../../../wizard/store";
import { ResponsiveSelect } from "../../ResponsiveSelect";

const KINDS: { value: GoalKind; label: string; description?: string }[] = [
  { value: "retirement", label: "Retirement", description: "Annual spend in retirement" },
  { value: "pre_retirement_spend", label: "Pre-retirement spend" },
  { value: "milestone", label: "Milestone", description: "One-off event" },
  { value: "education", label: "Education" },
  { value: "net_worth", label: "Net worth target" },
  { value: "gift", label: "Gift" },
];

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
          Add goals you want the projection to grade — e.g. "retire at 65 with €40k/year".
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
            options={KINDS}
            label="Goal kind"
          />
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Target amount (€)</span>
          <input
            type="number"
            inputMode="decimal"
            value={goal.target_amount}
            onChange={(e) => onChange({ target_amount: Number(e.target.value) })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Target year</span>
          <input
            type="number"
            inputMode="numeric"
            value={goal.target_year}
            onChange={(e) => onChange({ target_year: Number(e.target.value) })}
            style={inputStyle}
          />
        </label>
      </div>
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

const inputStyle: React.CSSProperties = {
  padding: "10px 12px",
  border: "1px solid #cbd5e1",
  borderRadius: 6,
  fontSize: 16,
  minHeight: 44,
};
