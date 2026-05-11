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
import { fmtMoney, fmtPctDisplay } from "../../lib/format";
import { useSoftDelete } from "../../lib/useSoftDelete";

const KINDS: { value: IncomeKind; label: string; defaultPaysPRSI: boolean; defaultPaysUSC: boolean }[] = [
  { value: "employment", label: "Employment (PAYE)", defaultPaysPRSI: true, defaultPaysUSC: true },
  { value: "self_employment", label: "Self-employment", defaultPaysPRSI: true, defaultPaysUSC: true },
  { value: "rental", label: "Rental income", defaultPaysPRSI: false, defaultPaysUSC: true },
  { value: "state_pension", label: "State pension", defaultPaysPRSI: false, defaultPaysUSC: false },
  { value: "private_pension_drawdown", label: "Private pension drawdown", defaultPaysPRSI: false, defaultPaysUSC: true },
  { value: "annuity", label: "Annuity", defaultPaysPRSI: false, defaultPaysUSC: true },
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
        <PersonIncomeBlock key={p.id} planId={planId} personId={p.id} personName={p.name} />
      ))}
    </div>
  );
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
  };
}

function PersonIncomeBlock({
  planId,
  personId,
  personName,
}: {
  planId: number;
  personId: number;
  personName: string;
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
    };
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    await create.mutateAsync(buildPayload(form));
  };

  const onSaveEdit = async () => {
    if (editingId === null || !editForm.name.trim()) return;
    await update.mutateAsync({ id: editingId, body: buildPayload(editForm) });
    setEditingId(null);
  };

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>{personName}</h3>

      <form onSubmit={onSubmit}>
        <FormFields form={form} setForm={setForm} />
        <button type="submit" className="btn" disabled={create.isPending}>
          Add
        </button>
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
        <table style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Gross / yr</th>
              <th>Years</th>
              <th>Escal.</th>
              <th>
                Pension %
                <HelpTip>
                  Employee pension contribution as a % of gross. Tax-relievable up to age-based caps
                  (15% under 30 → 40% age 60+) and the €115k earnings cap.
                </HelpTip>
              </th>
              <th>
                Employer %
                <HelpTip>
                  Employer's contribution to the pension wrapper, on top of yours. Doesn't reduce
                  your taxable income, doesn't count against the employee's age cap (but does count
                  toward the Standard Fund Threshold).
                </HelpTip>
              </th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.map((i) =>
              editingId === i.id ? (
                <tr key={i.id}>
                  <td colSpan={8}>
                    <FormFields form={editForm} setForm={setEditForm} />
                    <div className="row" style={{ marginTop: 8 }}>
                      <button className="btn" onClick={onSaveEdit} disabled={update.isPending}>
                        Save
                      </button>
                      <button
                        className="btn btn-secondary"
                        onClick={() => setEditingId(null)}
                        type="button"
                      >
                        Cancel
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr key={i.id}>
                  <td>{i.name}</td>
                  <td className="muted">{KINDS.find((k) => k.value === i.kind)?.label ?? i.kind}</td>
                  <td>{fmtMoney(i.gross_amount)}</td>
                  <td>
                    {i.start_year}
                    {i.end_year ? `–${i.end_year}` : "→"}
                  </td>
                  <td>{fmtPctDisplay(i.escalation_rate)}</td>
                  <td>
                    {i.pension_contribution_pct > 0 ? fmtPctDisplay(i.pension_contribution_pct) : "—"}
                  </td>
                  <td>
                    {i.employer_pension_contribution_pct > 0
                      ? fmtPctDisplay(i.employer_pension_contribution_pct)
                      : "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
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
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      )}
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
    </div>
  );
}
