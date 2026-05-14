import { useEffect, useState } from "react";

import {
  useChildren,
  useCreateChild,
  useDeleteChild,
  usePeople,
  useUpdateChild,
} from "../../api/hooks";
import type { Child, ChildCreate } from "../../api/types";
import { EditModal } from "../../components/EditModal";
import { EmptyState } from "../../components/EmptyState";
import { HelpTip } from "../../components/HelpTip";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { useSoftDelete } from "../../lib/useSoftDelete";

type FormState = {
  name: string;
  dob: string;
  primary_carer_id: number | "";
};

const blankForm: FormState = {
  name: "",
  dob: "2020-01-01",
  primary_carer_id: "",
};

function fromChild(c: Child): FormState {
  return {
    name: c.name,
    dob: c.dob,
    primary_carer_id: c.primary_carer_id ?? "",
  };
}

export function ChildrenPane({ planId }: { planId: number }) {
  const { data: people } = usePeople(planId);
  const { data: children, isLoading } = useChildren(planId);
  const create = useCreateChild(planId);
  const update = useUpdateChild(planId);
  const del = useDeleteChild(planId);

  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(blankForm);

  const softDelete = useSoftDelete<Child, ChildCreate>({
    describe: (c) => `"${c.name}"`,
    toPayload: (c) => ({
      name: c.name,
      dob: c.dob,
      primary_carer_id: c.primary_carer_id,
    }),
    remove: (id) => del.mutate(id),
    recreate: (payload) => create.mutate(payload),
  });

  useEffect(() => {
    if (editingId === null || !children) return;
    const row = children.find((c) => c.id === editingId);
    if (row) setEditForm(fromChild(row));
  }, [editingId, children]);

  const buildPayload = (f: FormState): ChildCreate => ({
    name: f.name.trim(),
    dob: f.dob,
    primary_carer_id: f.primary_carer_id === "" ? null : Number(f.primary_carer_id),
  });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    await create.mutateAsync(buildPayload(form));
    setForm(blankForm);
  };

  const onSaveEdit = async () => {
    if (editingId === null || !editForm.name.trim()) return;
    await update.mutateAsync({ id: editingId, body: buildPayload(editForm) });
    setEditingId(null);
  };

  const carerName = (id: number | null) =>
    id == null ? "—" : people?.find((p) => p.id === id)?.name ?? "(removed)";

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>
          Add child
          <HelpTip>
            Child entities are separate from the household's People. They drive Child Benefit
            (€140/mo per child under 18, tax-free, paid to the primary carer) and will be hooked
            into future features like education goals and CAT Group A tracking.
          </HelpTip>
        </h3>
        <form onSubmit={onSubmit}>
          <ChildFields form={form} setForm={setForm} carers={people ?? []} />
          <button type="submit" className="btn" disabled={create.isPending}>
            Add
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Children</h3>
        {isLoading && <p className="muted">Loading…</p>}
        {children && children.length === 0 && (
          <EmptyState
            title="No children added yet."
            hint="Add a child to enable Child Benefit payments in the projection. Existing plans without children are unaffected."
          />
        )}
        {children && children.length > 0 && (
          <ResponsiveTable<Child>
            rows={children}
            getKey={(c) => c.id}
            cardTitle={(c) => c.name}
            columns={[
              { header: "Name", cell: (c) => c.name, hideOnMobile: true },
              { header: "DOB", cell: (c) => c.dob },
              { header: "Carer", cell: (c) => carerName(c.primary_carer_id) },
            ]}
            renderActions={(c) => (
              <>
                <button
                  className="btn btn-secondary"
                  style={{ marginRight: 6 }}
                  onClick={() => setEditingId(c.id)}
                >
                  Edit
                </button>
                <button className="btn btn-secondary" onClick={() => softDelete(c, c.id)}>
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
        title="Edit child"
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
        <ChildFields form={editForm} setForm={setEditForm} carers={people ?? []} />
      </EditModal>
    </div>
  );
}

function ChildFields({
  form,
  setForm,
  carers,
}: {
  form: FormState;
  setForm: (f: FormState) => void;
  carers: { id: number; name: string }[];
}) {
  return (
    <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
      <div className="field" style={{ flex: "2 1 200px", minWidth: 200 }}>
        <label>Name</label>
        <input
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="e.g. Saoirse"
          required
        />
      </div>
      <div className="field" style={{ flex: "1 1 140px", minWidth: 140 }}>
        <label>Date of birth</label>
        <input
          type="date"
          value={form.dob}
          onChange={(e) => setForm({ ...form, dob: e.target.value })}
          required
        />
      </div>
      <div className="field" style={{ flex: "1 1 160px", minWidth: 160 }}>
        <label>
          Primary carer
          <HelpTip>
            Person who receives the Child Benefit payment. Leave blank to pay it to the plan's
            primary person.
          </HelpTip>
        </label>
        <select
          value={form.primary_carer_id}
          onChange={(e) =>
            setForm({
              ...form,
              primary_carer_id: e.target.value === "" ? "" : Number(e.target.value),
            })
          }
        >
          <option value="">— Primary —</option>
          {carers.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
