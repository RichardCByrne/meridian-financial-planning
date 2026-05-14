import type { IncomeKind } from "../../../api/types";
import { useWizard, type DraftId, type IncomeDraft } from "../../../wizard/store";
import { HelpTip } from "../../HelpTip";
import { NumericInput } from "../../NumericInput";
import { ResponsiveSelect } from "../../ResponsiveSelect";

const INCOME_KINDS: { value: IncomeKind; label: string; description?: string }[] = [
  { value: "employment", label: "Employment", description: "Salary, PAYE" },
  { value: "self_employment", label: "Self-employment", description: "Schedule D" },
  { value: "rental", label: "Rental", description: "Investment property income" },
  { value: "state_pension", label: "State pension" },
  { value: "private_pension_drawdown", label: "Private pension drawdown" },
  { value: "annuity", label: "Annuity" },
  { value: "homecaring", label: "Home-caring" },
  { value: "other", label: "Other" },
];

export function IncomeStep() {
  const people = useWizard((s) => s.people);
  const incomes = useWizard((s) => s.incomes);
  const plan = useWizard((s) => s.plan);
  const addIncome = useWizard((s) => s.addIncome);
  const updateIncome = useWizard((s) => s.updateIncome);
  const removeIncome = useWizard((s) => s.removeIncome);

  const baseYear = plan.base_year ?? new Date().getFullYear();

  if (people.length === 0) {
    return (
      <div className="card">
        <p>No people yet. Go back and add at least one person.</p>
      </div>
    );
  }

  const onAddSalary = (personDraftId: DraftId) => {
    addIncome({
      personDraftId,
      kind: "employment",
      name: "Salary",
      gross_amount: 0,
      start_year: baseYear,
      end_year: null,
      escalation_rate: 0.03,
      pays_prsi: true,
      pays_usc: true,
      pension_contribution_pct: 0,
      employer_pension_contribution_pct: 0,
    });
  };

  const onAddBonus = (personDraftId: DraftId) => {
    addIncome({
      personDraftId,
      kind: "other",
      name: `${baseYear} bonus`,
      gross_amount: 0,
      start_year: baseYear,
      end_year: baseYear,
      escalation_rate: 0,
      pays_prsi: true,
      pays_usc: true,
      pension_contribution_pct: 0,
      employer_pension_contribution_pct: 0,
      isBonus: true,
    });
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {people.map((person) => {
        const personIncomes = incomes.filter((i) => i.personDraftId === person.draftId);
        return (
          <div key={person.draftId} style={{ display: "grid", gap: 10 }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>{person.name || "Unnamed person"}</h3>
            {personIncomes.map((i) => (
              <IncomeRow
                key={i.draftId}
                income={i}
                onChange={(patch) => updateIncome(i.draftId, patch)}
                onRemove={() => removeIncome(i.draftId)}
              />
            ))}
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => onAddSalary(person.draftId)}
                style={{ minHeight: 44 }}
              >
                + Add income
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => onAddBonus(person.draftId)}
                style={{ minHeight: 44 }}
                title="One-year taxable bonus"
              >
                + Add bonus
              </button>
            </div>
          </div>
        );
      })}
      <p className="muted" style={{ fontSize: 13, color: "#64748b" }}>
        A bonus is added as taxable other income so PAYE/USC/PRSI apply correctly. Defaults to a
        single year — set a later end year to repeat it. For a non-taxable windfall (gift,
        inheritance), add it as a cash asset later.
      </p>
    </div>
  );
}

function IncomeRow({
  income,
  onChange,
  onRemove,
}: {
  income: IncomeDraft;
  onChange: (patch: Partial<IncomeDraft>) => void;
  onRemove: () => void;
}) {
  const growthPct = Math.round(((income.escalation_rate ?? 0) * 100) * 100) / 100;
  return (
    <div className="card" style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Name</span>
          <input
            value={income.name}
            onChange={(e) => onChange({ name: e.target.value })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Kind</span>
          <ResponsiveSelect<IncomeKind>
            value={income.kind}
            onChange={(v) => onChange({ kind: v })}
            options={INCOME_KINDS}
            label="Income kind"
          />
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Gross (€/year)</span>
          <NumericInput
            value={income.gross_amount}
            onChange={(v) => onChange({ gross_amount: Number.isFinite(v) ? v : 0 })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Start year</span>
          <NumericInput
            integer
            value={income.start_year}
            onChange={(v) => onChange({ start_year: Number.isFinite(v) ? v : income.start_year })}
            style={inputStyle}
          />
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 }}>
            End year (optional)
            <HelpTip>
              Leave blank to run indefinitely. Earned income (employment / self-employment) stops
              automatically at the owner's retirement age regardless of what you set here. Passive
              income (rental, annuity, other) keeps flowing past retirement unless you set an end
              year. State pension and ARF drawdowns are injected by the engine separately and
              ignore this field.
            </HelpTip>
          </span>
          <NumericInput
            integer
            value={income.end_year ?? NaN}
            onChange={(v) => onChange({ end_year: Number.isFinite(v) ? v : null })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Average annual growth (%)</span>
          <NumericInput
            value={growthPct}
            onChange={(v) =>
              onChange({ escalation_rate: Number.isFinite(v) ? v / 100 : 0 })
            }
            style={inputStyle}
          />
        </label>
      </div>
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
