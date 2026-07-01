import { useEffect, useState } from "react";

import {
  useCreateDBPension,
  useDeleteDBPension,
  useDBPensions,
  usePeople,
  useUpdateDBPension,
} from "../../api/hooks";
import type { DBPension, DBPensionCreate } from "../../api/types";
import { EditModal } from "../../components/EditModal";
import { EmptyState } from "../../components/EmptyState";
import { HelpTip } from "../../components/HelpTip";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { fmtMoney } from "../../lib/format";
import { useSoftDelete } from "../../lib/useSoftDelete";

type FormState = {
  person_id: number | "";
  name: string;
  accrual_denominator: number; // 60 → 1/60 accrual
  service_years: number;
  final_salary: number;
  revaluation_rate: number; // fraction
  normal_retirement_age: number;
  tax_free_lump_sum: number;
};

const blankForm: FormState = {
  person_id: "",
  name: "",
  accrual_denominator: 60,
  service_years: 40,
  final_salary: 60_000,
  revaluation_rate: 0,
  normal_retirement_age: 65,
  tax_free_lump_sum: 0,
};

function fromPension(p: DBPension): FormState {
  return {
    person_id: p.person_id,
    name: p.name,
    accrual_denominator: p.accrual_rate > 0 ? Math.round(1 / p.accrual_rate) : 60,
    service_years: p.service_years,
    final_salary: p.final_salary,
    revaluation_rate: p.revaluation_rate,
    normal_retirement_age: p.normal_retirement_age,
    tax_free_lump_sum: p.tax_free_lump_sum,
  };
}

const annualPension = (p: DBPension) => p.accrual_rate * p.service_years * p.final_salary;

export function DBPensionsPane({ planId }: { planId: number }) {
  const { data: people } = usePeople(planId);
  const { data: pensions, isLoading } = useDBPensions(planId);
  const create = useCreateDBPension(planId);
  const update = useUpdateDBPension(planId);
  const del = useDeleteDBPension(planId);

  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(blankForm);

  useEffect(() => {
    if (form.person_id === "" && people && people.length > 0) {
      setForm((f) => ({ ...f, person_id: people[0].id }));
    }
  }, [people, form.person_id]);

  const softDelete = useSoftDelete<DBPension, DBPensionCreate>({
    describe: (p) => `"${p.name}"`,
    toPayload: (p) => ({
      person_id: p.person_id,
      name: p.name,
      accrual_rate: p.accrual_rate,
      service_years: p.service_years,
      final_salary: p.final_salary,
      revaluation_rate: p.revaluation_rate,
      normal_retirement_age: p.normal_retirement_age,
      tax_free_lump_sum: p.tax_free_lump_sum,
    }),
    remove: (id) => del.mutate(id),
    recreate: (payload) => create.mutate(payload),
  });

  useEffect(() => {
    if (editingId === null || !pensions) return;
    const row = pensions.find((p) => p.id === editingId);
    if (row) setEditForm(fromPension(row));
  }, [editingId, pensions]);

  const buildPayload = (f: FormState): DBPensionCreate => ({
    person_id: f.person_id === "" ? 0 : Number(f.person_id),
    name: f.name.trim(),
    accrual_rate: f.accrual_denominator > 0 ? 1 / f.accrual_denominator : 0,
    service_years: Math.max(0, f.service_years),
    final_salary: Math.max(0, f.final_salary),
    revaluation_rate: Math.max(0, f.revaluation_rate),
    normal_retirement_age: f.normal_retirement_age,
    tax_free_lump_sum: Math.max(0, f.tax_free_lump_sum),
  });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || form.person_id === "") return;
    await create.mutateAsync(buildPayload(form));
    setForm({ ...blankForm, person_id: form.person_id });
  };

  const onSaveEdit = async () => {
    if (editingId === null || !editForm.name.trim() || editForm.person_id === "") return;
    await update.mutateAsync({ id: editingId, body: buildPayload(editForm) });
    setEditingId(null);
  };

  const personName = (id: number) => people?.find((p) => p.id === id)?.name ?? "(removed)";

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>
          Add defined-benefit pension
          <HelpTip>
            A final-salary / defined-benefit scheme pays a guaranteed income for life from its
            normal retirement age, worked out as <b>accrual rate × years of service × final
            salary</b> (e.g. 1/60 × 40 × €60,000 = €40,000/yr). It’s taxed as PAYE income but
            is PRSI-exempt, and can revalue with inflation. Model any tax-free lump sum
            separately. Use this for public-service and older company pensions — not for a
            defined-contribution PRSA/pot (add those as pension assets instead).
          </HelpTip>
        </h3>
        <form onSubmit={onSubmit}>
          <PensionFields form={form} setForm={setForm} people={people ?? []} />
          <button type="submit" className="btn" disabled={create.isPending}>
            Add
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Defined-benefit pensions</h3>
        {isLoading && <p className="muted">Loading…</p>}
        {pensions && pensions.length === 0 && (
          <EmptyState
            title="No defined-benefit pensions yet."
            hint="Add a final-salary or public-service scheme to project its guaranteed retirement income."
          />
        )}
        {pensions && pensions.length > 0 && (
          <ResponsiveTable<DBPension>
            rows={pensions}
            getKey={(p) => p.id}
            cardTitle={(p) => p.name}
            columns={[
              { header: "Name", cell: (p) => p.name, hideOnMobile: true },
              { header: "Member", cell: (p) => personName(p.person_id) },
              { header: "Annual pension", cell: (p) => fmtMoney(annualPension(p)) },
              { header: "From age", cell: (p) => p.normal_retirement_age },
              {
                header: "Lump sum",
                cell: (p) => (p.tax_free_lump_sum > 0 ? fmtMoney(p.tax_free_lump_sum) : "—"),
              },
            ]}
            renderActions={(p) => (
              <>
                <button
                  className="btn btn-secondary"
                  style={{ marginRight: 6 }}
                  onClick={() => setEditingId(p.id)}
                >
                  Edit
                </button>
                <button className="btn btn-secondary" onClick={() => softDelete(p, p.id)}>
                  Remove
                </button>
              </>
            )}
          />
        )}
      </div>

      <EditModal
        open={editingId !== null}
        onClose={() => setEditingId(null)}
        title="Edit DB pension"
        footer={
          <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
            <button className="btn btn-secondary" onClick={() => setEditingId(null)} type="button">
              Cancel
            </button>
            <button className="btn" onClick={onSaveEdit} disabled={update.isPending}>
              Save
            </button>
          </div>
        }
      >
        <PensionFields form={editForm} setForm={setEditForm} people={people ?? []} />
      </EditModal>
    </div>
  );
}

function PensionFields({
  form,
  setForm,
  people,
}: {
  form: FormState;
  setForm: (f: FormState) => void;
  people: { id: number; name: string }[];
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
        <div className="field" style={{ flex: "2 1 200px", minWidth: 180 }}>
          <label>Name</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. HSE pension"
            required
          />
        </div>
        <div className="field" style={{ flex: "1 1 150px", minWidth: 150 }}>
          <label>Member</label>
          <select
            value={form.person_id}
            onChange={(e) =>
              setForm({ ...form, person_id: e.target.value === "" ? "" : Number(e.target.value) })
            }
          >
            <option value="">— Select —</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
        <div className="field" style={{ flex: "1 1 120px", minWidth: 120 }}>
          <label>
            Accrual 1/N
            <HelpTip>Fraction of final salary earned per year of service. 60 means 1/60 (a common rate).</HelpTip>
          </label>
          <input
            type="number"
            min={1}
            value={form.accrual_denominator}
            onChange={(e) => setForm({ ...form, accrual_denominator: Number(e.target.value) })}
          />
        </div>
        <div className="field" style={{ flex: "1 1 120px", minWidth: 120 }}>
          <label>Service years</label>
          <input
            type="number"
            min={0}
            value={form.service_years}
            onChange={(e) => setForm({ ...form, service_years: Number(e.target.value) })}
          />
        </div>
        <div className="field" style={{ flex: "1 1 150px", minWidth: 150 }}>
          <label>Final salary (€)</label>
          <input
            type="number"
            min={0}
            value={form.final_salary}
            onChange={(e) => setForm({ ...form, final_salary: Number(e.target.value) })}
          />
        </div>
      </div>

      <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
        <div className="field" style={{ flex: "1 1 120px", minWidth: 120 }}>
          <label>
            Revaluation %
            <HelpTip>Annual indexation of the pension, in deferment and in payment.</HelpTip>
          </label>
          <input
            type="number"
            step={0.5}
            value={form.revaluation_rate * 100}
            onChange={(e) => setForm({ ...form, revaluation_rate: Number(e.target.value) / 100 })}
          />
        </div>
        <div className="field" style={{ flex: "1 1 120px", minWidth: 120 }}>
          <label>Retirement age</label>
          <input
            type="number"
            value={form.normal_retirement_age}
            onChange={(e) => setForm({ ...form, normal_retirement_age: Number(e.target.value) })}
          />
        </div>
        <div className="field" style={{ flex: "1 1 150px", minWidth: 150 }}>
          <label>
            Tax-free lump sum (€)
            <HelpTip>Optional one-off lump sum paid at retirement (0 = none).</HelpTip>
          </label>
          <input
            type="number"
            min={0}
            value={form.tax_free_lump_sum}
            onChange={(e) => setForm({ ...form, tax_free_lump_sum: Number(e.target.value) })}
          />
        </div>
      </div>
    </div>
  );
}
