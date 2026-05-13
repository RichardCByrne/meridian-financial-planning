import { useEffect, useState } from "react";

import { NumericInput } from "../../components/NumericInput";

import {
  useCreateGoal,
  useDeleteGoal,
  useGoals,
  usePeople,
  usePlan,
  useProjection,
  useUpdateGoal,
} from "../../api/hooks";
import type { Goal, GoalCreate, GoalKind } from "../../api/types";
import { HelpTip } from "../../components/HelpTip";
import { EmptyState } from "../../components/EmptyState";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { EditModal } from "../../components/EditModal";
import { fmtMoney } from "../../lib/format";
import { useSoftDelete } from "../../lib/useSoftDelete";

const KINDS: { value: GoalKind; label: string; help: string; costBearing: boolean }[] = [
  {
    value: "milestone",
    label: "Milestone",
    help: "One-shot spend in target year (e.g. car, wedding). Adds to expenses.",
    costBearing: true,
  },
  {
    value: "education",
    label: "Education",
    help: "Tuition / school fees. One-shot in target year (extend with recurring expenses).",
    costBearing: true,
  },
  {
    value: "gift",
    label: "Gift / inheritance",
    help: "One-shot transfer out in target year. Adds to expenses.",
    costBearing: true,
  },
  {
    value: "pre_retirement_spend",
    label: "Pre-retirement spend",
    help: "One-shot spend before retirement (e.g. lump-sum holiday). Adds to expenses.",
    costBearing: true,
  },
  {
    value: "net_worth",
    label: "Net worth target",
    help: "Aspirational. Achieved if your net worth meets the target by the target year.",
    costBearing: false,
  },
  {
    value: "retirement",
    label: "Retirement marker",
    help: "Informational marker on the timeline. Person.retirement_age drives the actual event.",
    costBearing: false,
  },
];

type FormState = {
  kind: GoalKind;
  name: string;
  target_amount: number;
  target_year: number;
  linked_person_id: number | null;
  notes: string;
};

const blankForm: FormState = {
  kind: "milestone",
  name: "New car",
  target_amount: 30_000,
  target_year: 2030,
  linked_person_id: null,
  notes: "",
};

function fromGoal(g: Goal): FormState {
  return {
    kind: g.kind,
    name: g.name,
    target_amount: g.target_amount,
    target_year: g.target_year,
    linked_person_id: g.linked_person_id,
    notes: g.notes ?? "",
  };
}

export function GoalsPane({ planId }: { planId: number }) {
  const { data, isLoading } = useGoals(planId);
  const { data: people } = usePeople(planId);
  const { data: plan } = usePlan(planId);
  const { data: projection } = useProjection(planId);
  const horizon: [number, number] | null = plan
    ? [plan.base_year, plan.base_year + plan.projection_years - 1]
    : null;
  const create = useCreateGoal(planId);
  const update = useUpdateGoal(planId);
  const del = useDeleteGoal(planId);

  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(blankForm);

  const softDelete = useSoftDelete<Goal, GoalCreate>({
    describe: (g) => `goal "${g.name}"`,
    toPayload: (g) => ({
      kind: g.kind,
      name: g.name,
      target_amount: g.target_amount,
      target_year: g.target_year,
      linked_person_id: g.linked_person_id,
      notes: g.notes,
    }),
    remove: (id) => del.mutate(id),
    recreate: (payload) => create.mutate(payload),
  });

  useEffect(() => {
    if (editingId === null || !data) return;
    const row = data.find((d) => d.id === editingId);
    if (row) setEditForm(fromGoal(row));
  }, [editingId, data]);

  const buildPayload = (f: FormState) => ({
    kind: f.kind,
    name: f.name.trim(),
    target_amount: f.target_amount,
    target_year: f.target_year,
    linked_person_id: f.linked_person_id,
    notes: f.notes.trim() || null,
  });

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

  const statusForGoal = (goalId: number, targetYear: number): string => {
    const row = projection?.years.find((y) => y.year === targetYear);
    return row?.goal_status?.[goalId] ?? "—";
  };

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Add goal</h3>
        <form onSubmit={onSubmit}>
          <FormFields form={form} setForm={setForm} people={people ?? []} horizon={horizon} />
          <button type="submit" className="btn" disabled={create.isPending}>
            Add
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Goals</h3>
        {isLoading && <p className="muted">Loading…</p>}
        {data && data.length === 0 && (
          <EmptyState
            title="Goals are optional — but they make the projection meaningful."
            hint="A goal is a target (retirement spend, a house deposit, a gift) the projection tracks against. Cost-bearing goals (like 'pay for college in 2034') inject as one-off expenses."
          />
        )}
        {data && data.length > 0 && (
          <ResponsiveTable<Goal>
            rows={data}
            getKey={(g) => g.id}
            cardTitle={(g) => g.name}
            columns={[
              { header: "Name", cell: (g) => g.name, hideOnMobile: true },
              {
                header: "Type",
                cell: (g) => (
                  <span className="muted">
                    {KINDS.find((k) => k.value === g.kind)?.label ?? g.kind}
                  </span>
                ),
              },
              {
                header: "Target",
                cell: (g) => (g.target_amount > 0 ? fmtMoney(g.target_amount) : "—"),
              },
              { header: "Year", cell: (g) => g.target_year },
              {
                header: "Linked",
                cell: (g) => (
                  <span className="muted">
                    {g.linked_person_id
                      ? people?.find((p) => p.id === g.linked_person_id)?.name ?? "—"
                      : "—"}
                  </span>
                ),
              },
              {
                header: "Status",
                cell: (g) => <StatusBadge status={statusForGoal(g.id, g.target_year)} />,
                thExtra: (
                  <HelpTip>
                    Resolves at target year and stays sticky thereafter. Cost-bearing goals
                    (milestone, education, gift, pre-retirement spend): <strong>Achieved</strong> if
                    funded that year, <strong>Missed</strong> if the year ran into a shortfall.
                    Net-worth goals: <strong>Met</strong> if net worth ≥ target at the snapshot year,
                    <strong> Below target</strong> otherwise — this is a snapshot, not a guarantee
                    you stay above the threshold afterward.
                  </HelpTip>
                ),
              },
            ]}
            renderActions={(g) => (
              <>
                <button
                  className="btn btn-secondary"
                  style={{ marginRight: 6 }}
                  onClick={() => setEditingId(g.id)}
                >
                  Edit
                </button>
                <button className="btn btn-secondary" onClick={() => softDelete(g, g.id)}>
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
        title="Edit goal"
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
        <FormFields
          form={editForm}
          setForm={setEditForm}
          people={people ?? []}
          horizon={horizon}
        />
      </EditModal>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const META: Record<string, { label: string; bg: string; fg: string }> = {
    achieved: { label: "Achieved", bg: "#dcfce7", fg: "#166534" },
    met: { label: "Met", bg: "#dbeafe", fg: "#1e40af" },
    missed: { label: "Missed", bg: "#fee2e2", fg: "#991b1b" },
    below_target: { label: "Below target", bg: "#fef3c7", fg: "#92400e" },
    pending: { label: "Pending", bg: "#e2e8f0", fg: "#475569" },
  };
  const m = META[status] ?? { label: status, bg: "#e2e8f0", fg: "#475569" };
  return (
    <span
      style={{
        background: m.bg,
        color: m.fg,
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {m.label}
    </span>
  );
}

function FormFields({
  form,
  setForm,
  people,
  horizon,
}: {
  form: FormState;
  setForm: (f: FormState) => void;
  people: { id: number; name: string }[];
  horizon: [number, number] | null;
}) {
  const yearOutOfRange =
    horizon !== null && (form.target_year < horizon[0] || form.target_year > horizon[1]);
  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: "block", fontSize: 12, color: "#475569", marginBottom: 6 }}>
          What kind of goal?
        </label>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 8,
          }}
        >
          {KINDS.map((k) => {
            const selected = form.kind === k.value;
            return (
              <button
                key={k.value}
                type="button"
                onClick={() => setForm({ ...form, kind: k.value })}
                style={{
                  textAlign: "left",
                  padding: "8px 10px",
                  borderRadius: 6,
                  border: selected ? "2px solid #2563eb" : "1px solid #cbd5e1",
                  background: selected ? "#eff6ff" : "#fff",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 2 }}>{k.label}</div>
                <div className="muted" style={{ fontSize: 11, lineHeight: 1.3 }}>{k.help}</div>
              </button>
            );
          })}
        </div>
      </div>
    <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
      <div className="field" style={{ flex: 2, minWidth: 180 }}>
        <label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </div>
      <div className="field" style={{ flex: 1, minWidth: 120 }}>
        <label>Target (€)</label>
        <NumericInput
          value={form.target_amount}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, target_amount: v })}
        />
      </div>
      <div className="field" style={{ flex: 1, minWidth: 100 }}>
        <label>Target year</label>
        <NumericInput
          integer
          value={form.target_year}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, target_year: v })}
          style={yearOutOfRange ? { borderColor: "#dc2626" } : undefined}
        />
        {yearOutOfRange && horizon && (
          <span style={{ color: "#dc2626", fontSize: 11, marginTop: 2 }}>
            Outside plan horizon {horizon[0]}–{horizon[1]}. The server will reject this.
          </span>
        )}
      </div>
      <div className="field" style={{ flex: 1, minWidth: 140 }}>
        <label>Linked person</label>
        <select
          value={form.linked_person_id ?? ""}
          onChange={(e) =>
            setForm({
              ...form,
              linked_person_id: e.target.value === "" ? null : Number(e.target.value),
            })
          }
        >
          <option value="">—</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>
    </div>
    </div>
  );
}
