import { useEffect, useState } from "react";

import {
  useCreateLifePolicy,
  useDeleteLifePolicy,
  useLifePolicies,
  usePeople,
  useUpdateLifePolicy,
} from "../../api/hooks";
import type { LifePolicy, LifePolicyCreate, LifePolicyKind } from "../../api/types";
import { EditModal } from "../../components/EditModal";
import { EmptyState } from "../../components/EmptyState";
import { HelpTip } from "../../components/HelpTip";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { fmtMoney } from "../../lib/format";
import { useSoftDelete } from "../../lib/useSoftDelete";

const KIND_LABELS: Record<LifePolicyKind, string> = {
  term_life: "Term life",
  section_72: "Section 72 (CAT)",
};

const KIND_OPTIONS = Object.entries(KIND_LABELS) as [LifePolicyKind, string][];

type FormState = {
  person_id: number | "";
  name: string;
  kind: LifePolicyKind;
  sum_assured: number;
  premium_annual: number;
  start_year: number;
  end_year: number | "";
};

const blankForm: FormState = {
  person_id: "",
  name: "",
  kind: "term_life",
  sum_assured: 200_000,
  premium_annual: 600,
  start_year: new Date().getFullYear(),
  end_year: "",
};

function fromPolicy(p: LifePolicy): FormState {
  return {
    person_id: p.person_id,
    name: p.name,
    kind: p.kind,
    sum_assured: p.sum_assured,
    premium_annual: p.premium_annual,
    start_year: p.start_year,
    end_year: p.end_year ?? "",
  };
}

export function ProtectionPane({ planId }: { planId: number }) {
  const { data: people } = usePeople(planId);
  const { data: policies, isLoading } = useLifePolicies(planId);
  const create = useCreateLifePolicy(planId);
  const update = useUpdateLifePolicy(planId);
  const del = useDeleteLifePolicy(planId);

  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(blankForm);

  useEffect(() => {
    if (form.person_id === "" && people && people.length > 0) {
      setForm((f) => ({ ...f, person_id: people[0].id }));
    }
  }, [people, form.person_id]);

  const softDelete = useSoftDelete<LifePolicy, LifePolicyCreate>({
    describe: (p) => `"${p.name}"`,
    toPayload: (p) => ({
      person_id: p.person_id,
      name: p.name,
      kind: p.kind,
      sum_assured: p.sum_assured,
      premium_annual: p.premium_annual,
      start_year: p.start_year,
      end_year: p.end_year,
    }),
    remove: (id) => del.mutate(id),
    recreate: (payload) => create.mutate(payload),
  });

  useEffect(() => {
    if (editingId === null || !policies) return;
    const row = policies.find((p) => p.id === editingId);
    if (row) setEditForm(fromPolicy(row));
  }, [editingId, policies]);

  const buildPayload = (f: FormState): LifePolicyCreate => ({
    person_id: f.person_id === "" ? 0 : Number(f.person_id),
    name: f.name.trim(),
    kind: f.kind,
    sum_assured: Math.max(0, f.sum_assured),
    premium_annual: Math.max(0, f.premium_annual),
    start_year: f.start_year,
    end_year: f.end_year === "" ? null : Number(f.end_year),
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
          Add protection policy
          <HelpTip>
            Cover on one person, paid for by an annual premium out of cash while in force.
            <b> Term life</b> pays the sum assured tax-free to survivors if the insured dies
            within the term — offsetting lost income and clearing debt. <b>Section 72</b> is a
            Revenue-approved policy whose proceeds pay the inheritance CAT tax-free, so heirs
            keep the estate instead of selling assets to fund the bill. Model the death itself
            with a “dies in year” on the People tab, then see whether the cover closes the gap.
          </HelpTip>
        </h3>
        <form onSubmit={onSubmit}>
          <PolicyFields form={form} setForm={setForm} people={people ?? []} />
          <button type="submit" className="btn" disabled={create.isPending}>
            Add
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Protection policies</h3>
        {isLoading && <p className="muted">Loading…</p>}
        {policies && policies.length === 0 && (
          <EmptyState
            title="No protection policies yet."
            hint="Add term-life cover to model what your family receives if you die during the plan."
          />
        )}
        {policies && policies.length > 0 && (
          <ResponsiveTable<LifePolicy>
            rows={policies}
            getKey={(p) => p.id}
            cardTitle={(p) => p.name}
            columns={[
              { header: "Name", cell: (p) => p.name, hideOnMobile: true },
              { header: "Insured", cell: (p) => personName(p.person_id) },
              { header: "Kind", cell: (p) => KIND_LABELS[p.kind] },
              { header: "Sum assured", cell: (p) => fmtMoney(p.sum_assured) },
              { header: "Premium/yr", cell: (p) => fmtMoney(p.premium_annual) },
              { header: "Term", cell: (p) => `${p.start_year}–${p.end_year ?? "∞"}` },
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
        title="Edit policy"
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
        <PolicyFields form={editForm} setForm={setEditForm} people={people ?? []} />
      </EditModal>
    </div>
  );
}

function PolicyFields({
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
            placeholder="e.g. Mortgage protection"
            required
          />
        </div>
        <div className="field" style={{ flex: "1 1 150px", minWidth: 150 }}>
          <label>Insured person</label>
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
        <div className="field" style={{ flex: "1 1 160px", minWidth: 160 }}>
          <label>
            Kind
            <HelpTip>
              Term life pays survivors on death within the term. Section 72 is a Revenue-approved
              policy whose proceeds pay the inheritance CAT tax-free.
            </HelpTip>
          </label>
          <select
            value={form.kind}
            onChange={(e) => setForm({ ...form, kind: e.target.value as LifePolicyKind })}
          >
            {KIND_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
        <div className="field" style={{ flex: "1 1 160px", minWidth: 160 }}>
          <label>
            Sum assured (€)
            <HelpTip>
              {form.kind === "section_72"
                ? "Cover amount — the proceeds available to pay inheritance CAT tax-free."
                : "The tax-free lump sum paid to survivors if the insured dies within the term."}
            </HelpTip>
          </label>
          <input
            type="number"
            min={0}
            value={form.sum_assured}
            onChange={(e) => setForm({ ...form, sum_assured: Number(e.target.value) })}
          />
        </div>
        <div className="field" style={{ flex: "1 1 150px", minWidth: 150 }}>
          <label>Annual premium (€)</label>
          <input
            type="number"
            min={0}
            value={form.premium_annual}
            onChange={(e) => setForm({ ...form, premium_annual: Number(e.target.value) })}
          />
        </div>
      </div>

      <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
        <div className="field" style={{ flex: "1 1 110px", minWidth: 110 }}>
          <label>Start year</label>
          <input
            type="number"
            value={form.start_year}
            onChange={(e) => setForm({ ...form, start_year: Number(e.target.value) })}
          />
        </div>
        <div className="field" style={{ flex: "1 1 110px", minWidth: 110 }}>
          <label>
            End year
            <HelpTip>Leave blank for whole-of-life / open-ended cover.</HelpTip>
          </label>
          <input
            type="number"
            value={form.end_year}
            placeholder="∞"
            onChange={(e) =>
              setForm({ ...form, end_year: e.target.value === "" ? "" : Number(e.target.value) })
            }
          />
        </div>
      </div>
    </div>
  );
}
