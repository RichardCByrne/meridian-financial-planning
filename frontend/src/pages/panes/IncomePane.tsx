import { useEffect, useState } from "react";

import {
  useCreateIncome,
  useDeleteIncome,
  useIncomeFor,
  usePeople,
  useUpdateIncome,
} from "../../api/hooks";
import type { IncomeKind, IncomeSource } from "../../api/types";
import { HelpTip } from "../../components/HelpTip";
import { EmptyState } from "../../components/EmptyState";
import { JargonTerm } from "../../components/JargonTerm";
import { NumericInput } from "../../components/NumericInput";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { EditModal } from "../../components/EditModal";
import { fmtMoney, fmtPctDisplay } from "../../lib/format";
import { PaneTotal } from "../../components/PaneTotal";
import { useSoftDelete } from "../../lib/useSoftDelete";

const KINDS: { value: IncomeKind; label: string; defaultPaysPRSI: boolean; defaultPaysUSC: boolean }[] = [
  { value: "employment", label: "Employment (PAYE)", defaultPaysPRSI: true, defaultPaysUSC: true },
  { value: "self_employment", label: "Self-employment", defaultPaysPRSI: true, defaultPaysUSC: true },
  { value: "rental", label: "Rental income", defaultPaysPRSI: false, defaultPaysUSC: true },
  { value: "state_pension", label: "State pension", defaultPaysPRSI: false, defaultPaysUSC: false },
  { value: "private_pension_drawdown", label: "Private pension drawdown", defaultPaysPRSI: false, defaultPaysUSC: true },
  { value: "annuity", label: "Annuity", defaultPaysPRSI: false, defaultPaysUSC: true },
  { value: "homecaring", label: "HomeCaring (state pension credit only)", defaultPaysPRSI: false, defaultPaysUSC: false },
  { value: "other", label: "Other", defaultPaysPRSI: false, defaultPaysUSC: true },
];

export function IncomePane({ planId }: { planId: number }) {
  const { data: people } = usePeople(planId);

  if (!people || people.length === 0) {
    return (
      <EmptyState
        title="Add a person before assigning income."
        hint={
          <>
            Income is tracked per person so <JargonTerm term="PRSI" />,{" "}
            <JargonTerm term="USC" />, and pension caps apply correctly.{" "}
            <a href={`/plans/${planId}/people`}>Go to People →</a>
          </>
        }
      />
    );
  }

  return (
    <div>
      {people.map((p) => (
        <PersonIncomeBlock
          key={p.id}
          planId={planId}
          personId={p.id}
          personName={p.name}
          retirementYear={
            p.retirement_age != null
              ? new Date(p.dob).getFullYear() + p.retirement_age
              : null
          }
        />
      ))}
    </div>
  );
}

const EARNED_KINDS: IncomeKind[] = ["employment", "self_employment"];

function endsPastRetirement(
  kind: IncomeKind,
  startYear: number,
  endYear: number | null,
  retirementYear: number | null,
): boolean {
  if (retirementYear == null) return false;
  if (!EARNED_KINDS.includes(kind)) return false;
  // Income starts at/after retirement: engine drops it from year one, the
  // warning is noise — user already knows it won't pay.
  if (startYear >= retirementYear) return false;
  return endYear == null || endYear >= retirementYear;
}

type FormState = {
  kind: IncomeKind;
  name: string;
  gross_amount: number;
  start_year: number;
  end_year: number | "";
  escalation_rate: number;
  pension_contribution_pct: number;
  employer_pension_contribution_pct: number;
  is_bonus: boolean;
  rental_expenses_pct: number;
  furnishings_value: number;
};

const blankForm: FormState = {
  kind: "employment",
  name: "Salary",
  gross_amount: 50000,
  start_year: 2026,
  end_year: "",
  escalation_rate: 0.03,
  pension_contribution_pct: 0,
  employer_pension_contribution_pct: 0,
  is_bonus: false,
  rental_expenses_pct: 0,
  furnishings_value: 0,
};

function fromIncome(i: IncomeSource): FormState {
  return {
    kind: i.kind,
    name: i.name,
    gross_amount: i.gross_amount,
    start_year: i.start_year,
    end_year: i.end_year ?? "",
    escalation_rate: i.escalation_rate,
    pension_contribution_pct: i.pension_contribution_pct,
    employer_pension_contribution_pct: i.employer_pension_contribution_pct ?? 0,
    is_bonus: i.is_bonus ?? false,
    rental_expenses_pct: i.rental_expenses_pct ?? 0,
    furnishings_value: i.furnishings_value ?? 0,
  };
}

function PersonIncomeBlock({
  planId,
  personId,
  personName,
  retirementYear,
}: {
  planId: number;
  personId: number;
  personName: string;
  retirementYear: number | null;
}) {
  const { data, isLoading } = useIncomeFor(personId);
  const create = useCreateIncome(personId, planId);
  const update = useUpdateIncome(personId, planId);
  const del = useDeleteIncome(personId, planId);

  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(blankForm);

  const softDelete = useSoftDelete<IncomeSource, ReturnType<typeof buildPayload>>({
    describe: (i) => `income "${i.name}"`,
    toPayload: (i) => buildPayload(fromIncome(i)),
    remove: (id) => del.mutate(id),
    recreate: (payload) => create.mutate(payload),
  });

  useEffect(() => {
    if (editingId === null || !data) return;
    const row = data.find((d) => d.id === editingId);
    if (row) setEditForm(fromIncome(row));
  }, [editingId, data]);

  const buildPayload = (f: FormState) => {
    const kindMeta = KINDS.find((k) => k.value === f.kind)!;
    return {
      kind: f.kind,
      name: f.name.trim(),
      gross_amount: f.gross_amount,
      start_year: f.start_year,
      end_year: f.end_year === "" ? null : Number(f.end_year),
      escalation_rate: f.escalation_rate,
      pays_prsi: kindMeta.defaultPaysPRSI,
      pays_usc: kindMeta.defaultPaysUSC,
      pension_contribution_pct: f.pension_contribution_pct,
      employer_pension_contribution_pct: f.employer_pension_contribution_pct,
      is_bonus: f.is_bonus,
      rental_expenses_pct: f.kind === "rental" ? f.rental_expenses_pct : 0,
      furnishings_value: f.kind === "rental" ? f.furnishings_value : 0,
    };
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    await create.mutateAsync(buildPayload(form));
  };

  // One-click bonus: a single-year taxable "other" income flagged as a bonus.
  // Uses the gross/year currently in the form so the user can set the amount,
  // then click. Matches the plan wizard's "+ Add bonus".
  const onAddBonus = async () => {
    await create.mutateAsync({
      kind: "other",
      name: `${form.start_year} bonus`,
      gross_amount: form.gross_amount,
      start_year: form.start_year,
      end_year: form.start_year,
      escalation_rate: 0,
      pays_prsi: false,
      pays_usc: true,
      pension_contribution_pct: 0,
      employer_pension_contribution_pct: 0,
      is_bonus: true,
    });
  };

  const onSaveEdit = async () => {
    if (editingId === null || !editForm.name.trim()) return;
    await update.mutateAsync({ id: editingId, body: buildPayload(editForm) });
    setEditingId(null);
  };

  return (
    <div className="card">
      <div
        className="row"
        style={{ marginTop: 0, marginBottom: 8, alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}
      >
        <h3 style={{ margin: 0 }}>{personName}</h3>
        {data && data.length > 0 && (
          <PaneTotal
            label="Total gross"
            amount={data.reduce((s, i) => s + i.gross_amount, 0)}
            suffix="/ yr"
          />
        )}
      </div>

      <form onSubmit={onSubmit}>
        <FormFields form={form} setForm={setForm} />
        {endsPastRetirement(
          form.kind,
          Number(form.start_year),
          form.end_year === "" ? null : Number(form.end_year),
          retirementYear,
        ) && (
          <RetirementOverlapWarning
            retirementYear={retirementYear as number}
            personName={personName}
            inline
          />
        )}
        <div className="row" style={{ gap: 8 }}>
          <button type="submit" className="btn" disabled={create.isPending}>
            Add
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onAddBonus}
            disabled={create.isPending}
            title="Add a one-year taxable bonus (USC/PAYE apply). Uses the gross and start year above."
          >
            + Add bonus
          </button>
        </div>
      </form>

      {isLoading && <p className="muted">Loading…</p>}
      {data && data.length === 0 && (
        <EmptyState
          title={`Add income for ${personName}.`}
          hint={
            <>
              Employment and self-employment trigger <JargonTerm term="PRSI" />/
              <JargonTerm term="USC" /> and unlock pension tax relief. Pensions in payment and
              rental income are treated separately by Irish Revenue.
            </>
          }
        />
      )}
      {data && data.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <ResponsiveTable<IncomeSource>
            rows={data}
            getKey={(i) => i.id}
            cardTitle={(i) => (
              <>
                {i.name}
                {i.is_bonus && <BonusBadge />}
              </>
            )}
            columns={[
              {
                header: "Name",
                cell: (i) => (
                  <>
                    {i.name}
                    {i.is_bonus && <BonusBadge />}
                  </>
                ),
                hideOnMobile: true,
              },
              {
                header: "Type",
                cell: (i) => (
                  <span className="muted">
                    {KINDS.find((k) => k.value === i.kind)?.label ?? i.kind}
                  </span>
                ),
              },
              { header: "Gross / yr", cell: (i) => fmtMoney(i.gross_amount) },
              {
                header: "Years",
                cell: (i) => (
                  <>
                    {i.start_year}
                    {i.end_year ? `–${i.end_year}` : "→"}
                    {endsPastRetirement(i.kind, i.start_year, i.end_year, retirementYear) && (
                      <span
                        title={`${personName} retires in ${retirementYear}. Earned income is dropped at retirement regardless of end year.`}
                        style={{
                          marginLeft: 6,
                          color: "#92400e",
                          fontSize: 12,
                          fontWeight: 600,
                          cursor: "help",
                        }}
                      >
                        ⚠
                      </span>
                    )}
                  </>
                ),
              },
              { header: "Escal.", cell: (i) => fmtPctDisplay(i.escalation_rate) },
              {
                header: "Pension %",
                cell: (i) =>
                  i.pension_contribution_pct > 0
                    ? fmtPctDisplay(i.pension_contribution_pct)
                    : "—",
                thExtra: (
                  <HelpTip>
                    Employee pension contribution as a % of gross. Tax-relievable up to age-based caps
                    (15% under 30 → 40% age 60+) and the €115k earnings cap.
                  </HelpTip>
                ),
              },
              {
                header: "Employer %",
                cell: (i) =>
                  i.employer_pension_contribution_pct > 0
                    ? fmtPctDisplay(i.employer_pension_contribution_pct)
                    : "—",
                thExtra: (
                  <HelpTip>
                    Employer's contribution to the pension wrapper, on top of yours. Doesn't reduce
                    your taxable income, doesn't count against the employee's age cap (but does count
                    toward the Standard Fund Threshold).
                  </HelpTip>
                ),
              },
            ]}
            renderActions={(i) => (
              <>
                <button
                  className="btn btn-secondary"
                  style={{ marginRight: 6 }}
                  onClick={() => setEditingId(i.id)}
                >
                  Edit
                </button>
                <button className="btn btn-secondary" onClick={() => softDelete(i, i.id)}>
                  Remove
                </button>
              </>
            )}
          />
        </div>
      )}

      <EditModal
        open={editingId !== null}
        onClose={() => setEditingId(null)}
        title="Edit income"
        footer={
          <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
            <button
              className="btn btn-secondary"
              onClick={() => setEditingId(null)}
              type="button"
            >
              Cancel
            </button>
            <button className="btn" onClick={onSaveEdit} disabled={update.isPending}>
              Save
            </button>
          </div>
        }
      >
        <FormFields form={editForm} setForm={setEditForm} />
        {endsPastRetirement(
          editForm.kind,
          Number(editForm.start_year),
          editForm.end_year === "" ? null : Number(editForm.end_year),
          retirementYear,
        ) && (
          <RetirementOverlapWarning
            retirementYear={retirementYear as number}
            personName={personName}
          />
        )}
      </EditModal>
    </div>
  );
}

function BonusBadge() {
  return (
    <span
      title="One-off / annual bonus — taxed as normal income"
      style={{
        marginLeft: 6,
        padding: "1px 6px",
        fontSize: 11,
        fontWeight: 600,
        color: "#3730a3",
        background: "#e0e7ff",
        borderRadius: 999,
        verticalAlign: "middle",
      }}
    >
      Bonus
    </span>
  );
}

function RetirementOverlapWarning({
  retirementYear,
  personName,
  inline,
}: {
  retirementYear: number;
  personName: string;
  inline?: boolean;
}) {
  return (
    <div
      role="note"
      style={{
        marginTop: inline ? 8 : 12,
        marginBottom: inline ? 8 : 0,
        padding: "8px 12px",
        background: "#fef3c7",
        border: "1px solid #fbbf24",
        borderRadius: 6,
        color: "#92400e",
        fontSize: 13,
      }}
    >
      <strong>Heads up:</strong> {personName} retires in {retirementYear}. Earned income (employment
      and self-employment) is dropped at retirement regardless of end year, so this entry's
      post-retirement years won't pay. Use rental, annuity, or "other" if you mean for income to
      continue after retirement.
    </div>
  );
}

function FormFields({
  form,
  setForm,
}: {
  form: FormState;
  setForm: (f: FormState) => void;
}) {
  return (
    <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
      <div className="field" style={{ flex: "2 1 160px" }}>
        <label>Type</label>
        <select
          value={form.kind}
          onChange={(e) => setForm({ ...form, kind: e.target.value as IncomeKind })}
        >
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
      </div>
      <div className="field" style={{ flex: "2 1 160px" }}>
        <label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </div>
      <div className="field" style={{ flex: "1 1 100px" }}>
        <label>Gross / yr (€)</label>
        <NumericInput
          value={form.gross_amount}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, gross_amount: v })}
        />
      </div>
      <div className="field" style={{ flex: "1 1 80px" }}>
        <label>Start year</label>
        <NumericInput
          integer
          value={form.start_year}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, start_year: v })}
        />
      </div>
      <div className="field" style={{ flex: "1 1 80px" }}>
        <label>End year</label>
        <NumericInput
          integer
          value={form.end_year === "" ? NaN : form.end_year}
          placeholder="—"
          onChange={(v) => setForm({ ...form, end_year: Number.isFinite(v) ? v : "" })}
        />
      </div>
      <div className="field" style={{ flex: "1 1 80px" }}>
        <label>Escalation %</label>
        <NumericInput
          value={form.escalation_rate * 100}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, escalation_rate: v / 100 })}
        />
      </div>
      <div className="field" style={{ flex: "1 1 80px" }}>
        <label>
          Pension %
          <HelpTip>Employee contribution % of gross. Tax-relievable up to age cap.</HelpTip>
        </label>
        <NumericInput
          value={form.pension_contribution_pct * 100}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, pension_contribution_pct: v / 100 })}
        />
      </div>
      <div className="field" style={{ flex: "1 1 80px" }}>
        <label>
          Employer %
          <HelpTip>Employer contribution to the wrapper. Not subtracted from take-home.</HelpTip>
        </label>
        <NumericInput
          value={form.employer_pension_contribution_pct * 100}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, employer_pension_contribution_pct: v / 100 })}
        />
      </div>
      {form.kind === "rental" && (
        <>
          <div className="field" style={{ flex: "1 1 110px" }}>
            <label>
              Expenses %
              <HelpTip>
                Allowable expenses as a % of gross rent (mortgage interest, management, repairs,
                insurance). Deducted before tax — rental is taxed on profit, not gross.
              </HelpTip>
            </label>
            <NumericInput
              value={form.rental_expenses_pct * 100}
              onChange={(v) =>
                Number.isFinite(v) &&
                setForm({ ...form, rental_expenses_pct: Math.max(0, v) / 100 })
              }
            />
          </div>
          <div className="field" style={{ flex: "1 1 130px" }}>
            <label>
              Furnishings (€)
              <HelpTip>
                Value of furniture/fittings. Wear-and-tear capital allowance of 12.5%/yr for 8
                years reduces taxable rental profit.
              </HelpTip>
            </label>
            <NumericInput
              value={form.furnishings_value}
              onChange={(v) => Number.isFinite(v) && setForm({ ...form, furnishings_value: Math.max(0, v) })}
            />
          </div>
        </>
      )}
    </div>
  );
}
