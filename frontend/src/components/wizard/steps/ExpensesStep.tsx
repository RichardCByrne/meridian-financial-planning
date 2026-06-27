import type { ExpenseCategory } from "../../../api/types";
import { useWizard, type ExpenseDraft } from "../../../wizard/store";
import { HelpTip } from "../../HelpTip";
import { NumericInput } from "../../NumericInput";
import { ResponsiveSelect } from "../../ResponsiveSelect";

const CATEGORIES: { value: ExpenseCategory; label: string; description?: string }[] = [
  { value: "basic", label: "Basic", description: "Essential year-on-year living costs" },
  { value: "discretionary", label: "Discretionary", description: "Holidays, dining out, hobbies" },
  { value: "single_year", label: "One-off", description: "A single year (e.g. wedding)" },
];

export function ExpensesStep() {
  const expenses = useWizard((s) => s.expenses);
  const people = useWizard((s) => s.people);
  const plan = useWizard((s) => s.plan);
  const addExpense = useWizard((s) => s.addExpense);
  const updateExpense = useWizard((s) => s.updateExpense);
  const removeExpense = useWizard((s) => s.removeExpense);

  const baseYear = plan.base_year ?? new Date().getFullYear();

  const onAddBasic = () =>
    addExpense({
      name: "Household",
      category: "basic",
      amount: 0,
      start_year: baseYear,
      end_year: null,
      escalation_rate: 0.025,
      owner_person_id: null,
      ownerPersonDraftId: null,
    });

  const onAddDiscretionary = () =>
    addExpense({
      name: "Holidays",
      category: "discretionary",
      amount: 0,
      start_year: baseYear,
      end_year: null,
      escalation_rate: 0.025,
      owner_person_id: null,
      ownerPersonDraftId: null,
    });

  const onAddOneOff = () =>
    addExpense({
      name: "",
      category: "single_year",
      amount: 0,
      start_year: baseYear,
      end_year: baseYear,
      escalation_rate: 0,
      owner_person_id: null,
      ownerPersonDraftId: null,
    });

  const personOptions: { value: string; label: string }[] = [
    { value: "", label: "(household / unassigned)" },
    ...people.map((p) => ({ value: p.draftId, label: p.name || "Unnamed" })),
  ];

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {expenses.length === 0 && (
        <div className="muted" style={{ color: "#64748b" }}>
          Annual living costs the projection should subtract from income. Defaults: 2.5%
          inflation. Use "Legacy" for expenses that continue after a death (e.g. mortgage on a
          shared home). Use "One-off" for single-year items.
        </div>
      )}
      {expenses.map((e) => (
        <ExpenseRow
          key={e.draftId}
          expense={e}
          personOptions={personOptions}
          onChange={(patch) => updateExpense(e.draftId, patch)}
          onRemove={() => removeExpense(e.draftId)}
        />
      ))}
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onAddBasic}
          style={{ minHeight: 44 }}
        >
          + Add basic expense
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onAddDiscretionary}
          style={{ minHeight: 44 }}
        >
          + Add discretionary
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onAddOneOff}
          style={{ minHeight: 44 }}
        >
          + Add one-off
        </button>
      </div>
    </div>
  );
}

function ExpenseRow({
  expense,
  personOptions,
  onChange,
  onRemove,
}: {
  expense: ExpenseDraft;
  personOptions: { value: string; label: string }[];
  onChange: (patch: Partial<ExpenseDraft>) => void;
  onRemove: () => void;
}) {
  const growthPct = Math.round((expense.escalation_rate ?? 0) * 100 * 100) / 100;
  return (
    <div className="card" style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Name</span>
          <input
            value={expense.name}
            onChange={(e) => onChange({ name: e.target.value })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 }}>
            Category
            <HelpTip>
              <strong>Basic</strong> and <strong>Discretionary</strong> recur every year.{" "}
              <strong>One-off</strong> applies in a single year. <strong>Legacy</strong>{" "}
              continues after the owner dies (use for mortgage on a shared home, etc).
            </HelpTip>
          </span>
          <ResponsiveSelect<ExpenseCategory>
            value={expense.category}
            onChange={(v) => onChange({ category: v })}
            options={CATEGORIES}
            label="Category"
          />
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Amount (€/year)</span>
          <NumericInput
            value={expense.amount}
            onChange={(v) => onChange({ amount: Number.isFinite(v) ? v : 0 })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Start year</span>
          <NumericInput
            integer
            value={expense.start_year}
            onChange={(v) =>
              onChange({ start_year: Number.isFinite(v) ? v : expense.start_year })
            }
            style={inputStyle}
          />
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>End year (optional)</span>
          <NumericInput
            integer
            value={expense.end_year ?? NaN}
            onChange={(v) => onChange({ end_year: Number.isFinite(v) ? v : null })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Inflation (%)</span>
          <NumericInput
            value={growthPct}
            onChange={(v) =>
              onChange({ escalation_rate: Number.isFinite(v) ? v / 100 : 0 })
            }
            style={inputStyle}
          />
        </label>
      </div>
      <label style={{ display: "grid", gap: 4 }}>
        <span style={{ fontWeight: 600 }}>Owner (optional)</span>
        <ResponsiveSelect<string>
          value={expense.ownerPersonDraftId ?? ""}
          onChange={(v) => onChange({ ownerPersonDraftId: v === "" ? null : v })}
          options={personOptions}
          label="Owner"
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
