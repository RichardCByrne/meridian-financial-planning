import { useState } from "react";

import {
  useBequests,
  useCreateBequest,
  useDeleteBequest,
  usePeople,
  useProjection,
  useUpdateBequest,
} from "../../api/hooks";
import type { Bequest, BequestCreate, CatGroup } from "../../api/types";
import { HelpTip } from "../../components/HelpTip";
import { EmptyState } from "../../components/EmptyState";
import { JargonTerm } from "../../components/JargonTerm";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { EditModal } from "../../components/EditModal";
import { useSoftDelete } from "../../lib/useSoftDelete";
import { fmtMoney as fmt, fmtPctDisplay } from "../../lib/format";

const CAT_GROUP_LABELS: Record<CatGroup, string> = {
  A: "Group A — child / parent (€400k threshold)",
  B: "Group B — sibling / grandchild (€40k threshold)",
  C: "Group C — unrelated (€20k threshold)",
  exempt: "Exempt — spouse / civil partner",
};

const CAT_GROUP_OPTIONS: CatGroup[] = ["A", "B", "C", "exempt"];

function deathYear(dob: string, lifeExpectancy: number): number {
  return new Date(dob).getFullYear() + lifeExpectancy;
}

export function LegacyPane({ planId }: { planId: number }) {
  const { data: people } = usePeople(planId);
  const { data: bequests } = useBequests(planId);
  const { data: projection } = useProjection(planId);
  const createBequest = useCreateBequest(planId);
  const updateBequest = useUpdateBequest(planId);
  const deleteBequest = useDeleteBequest(planId);

  const [newBequest, setNewBequest] = useState<Partial<BequestCreate>>({
    cat_group: "A",
    share_pct: 1.0,
  });

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<Bequest>>({});

  if (!people || !bequests) return <p className="muted">Loading…</p>;

  const personName = (id: number | null) =>
    id == null ? "External (outside plan)" : (people.find((p) => p.id === id)?.name ?? `Person ${id}`);

  const onAdd = async () => {
    if (!newBequest.from_person_id || newBequest.share_pct == null) return;
    await createBequest.mutateAsync(newBequest as BequestCreate);
    setNewBequest({ cat_group: "A", share_pct: 1.0 });
  };

  const onSaveEdit = async () => {
    if (editingId == null) return;
    await updateBequest.mutateAsync({ id: editingId, body: editDraft });
    setEditingId(null);
    setEditDraft({});
  };

  const softDelete = useSoftDelete<Bequest, BequestCreate>({
    describe: (b) => `bequest to ${b.to_person_id == null ? "external" : `person ${b.to_person_id}`}`,
    toPayload: (b) => ({
      from_person_id: b.from_person_id,
      to_person_id: b.to_person_id,
      cat_group: b.cat_group,
      share_pct: b.share_pct,
      notes: b.notes,
    }),
    remove: (id) => deleteBequest.mutate(id),
    recreate: (payload) => createBequest.mutate(payload),
  });

  // Group bequests by from_person_id for display
  const bequestsByPerson = people.reduce<Record<number, Bequest[]>>((acc, p) => {
    acc[p.id] = bequests.filter((b) => b.from_person_id === p.id);
    return acc;
  }, {});

  // Find estate value for each person from projection data
  const estateByPerson: Record<number, number> = {};
  if (projection) {
    for (const year of projection.years) {
      for (const [personIdStr, value] of Object.entries(year.estate_transfers)) {
        const pid = Number(personIdStr);
        if (!(pid in estateByPerson)) {
          estateByPerson[pid] = value;
        }
      }
    }
  }

  return (
    <div>
      <div className="card pane-intro-card">
        <h3 style={{ marginTop: 0 }}>
          Legacy &amp; inheritance
          <HelpTip>
            Set up how each person's estate is distributed when they pass away (at their life
            expectancy age). Meridian computes Capital Acquisitions Tax (CAT) at the Group A/B/C
            thresholds from your tax rules and shows the net inheritance in the projection. Use
            the "exempt" group for a spouse — no CAT regardless of amount.
          </HelpTip>
        </h3>
        <p className="muted pane-intro-prose" style={{ marginTop: 0 }}>
          Allocate shares of each person's projected estate to beneficiaries. Unallocated shares
          leave the plan. Internal beneficiaries (people in this plan) receive the net amount after{" "}
          <JargonTerm term="CAT" />; external beneficiaries remove the value from the plan entirely.
        </p>
      </div>

      {people.map((person) => {
        const myBequests = bequestsByPerson[person.id] ?? [];
        const estateValue = estateByPerson[person.id];
        const totalAllocated = myBequests.reduce((s, b) => s + b.share_pct, 0);
        const dyear = deathYear(person.dob, person.life_expectancy);

        return (
          <div key={person.id} className="card">
            <h4 style={{ marginTop: 0, marginBottom: 4 }}>
              {person.name}
              <span className="muted" style={{ fontWeight: 400, marginLeft: 8, fontSize: 13 }}>
                dies {dyear} (age {person.life_expectancy})
              </span>
            </h4>
            {estateValue != null && (
              <p style={{ marginTop: 0, marginBottom: 8 }} className="muted">
                Projected estate at death:{" "}
                <strong style={{ color: "#0f172a" }}>{fmt(estateValue)}</strong>
              </p>
            )}
            {totalAllocated > 1.0001 && (
              <p style={{ color: "#dc2626", marginTop: 0, marginBottom: 8, fontSize: 13 }}>
                ⚠ Allocations total {fmtPctDisplay(totalAllocated)} — reduce to 100% or
                below.
              </p>
            )}

            {myBequests.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <ResponsiveTable<Bequest>
                  rows={myBequests}
                  getKey={(b) => b.id}
                  cardTitle={(b) => personName(b.to_person_id)}
                  columns={[
                    { header: "To", cell: (b) => personName(b.to_person_id), hideOnMobile: true },
                    { header: "Share", cell: (b) => fmtPctDisplay(b.share_pct) },
                    {
                      header: "CAT group",
                      cell: (b) => (
                        <span title={CAT_GROUP_LABELS[b.cat_group as CatGroup]}>{b.cat_group}</span>
                      ),
                    },
                    {
                      header: "Notes",
                      cell: (b) => <span className="muted">{b.notes || "—"}</span>,
                    },
                  ]}
                  renderActions={(b) => (
                    <>
                      <button
                        className="btn btn-secondary"
                        style={{ marginRight: 6 }}
                        onClick={() => {
                          setEditingId(b.id);
                          setEditDraft({
                            to_person_id: b.to_person_id,
                            share_pct: b.share_pct,
                            cat_group: b.cat_group as CatGroup,
                            notes: b.notes,
                          });
                        }}
                      >
                        Edit
                      </button>
                      <button
                        className="btn btn-secondary"
                        style={{ color: "#dc2626" }}
                        onClick={() => softDelete(b, b.id)}
                      >
                        Delete
                      </button>
                    </>
                  )}
                />
              </div>
            )}

            {/* Add new bequest form for this person */}
            <details>
              <summary
                style={{ cursor: "pointer", fontSize: 13, color: "#2563eb", userSelect: "none" }}
              >
                + Add bequest
              </summary>
              <div
                className="row"
                style={{ flexWrap: "wrap", gap: 8, marginTop: 8, alignItems: "flex-end" }}
              >
                <div className="field" style={{ minWidth: 160 }}>
                  <label>To</label>
                  <select
                    value={newBequest.from_person_id === person.id
                      ? (newBequest.to_person_id ?? "")
                      : ""}
                    onChange={(e) =>
                      setNewBequest({
                        ...newBequest,
                        from_person_id: person.id,
                        to_person_id: e.target.value === "" ? null : Number(e.target.value),
                      })
                    }
                  >
                    <option value="">External</option>
                    {people
                      .filter((p) => p.id !== person.id)
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                  </select>
                </div>
                <div className="field" style={{ minWidth: 100 }}>
                  <label>Share %</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={1}
                    value={(newBequest.from_person_id === person.id ? (newBequest.share_pct ?? 1) : 1) * 100}
                    onChange={(e) =>
                      setNewBequest({
                        ...newBequest,
                        from_person_id: person.id,
                        share_pct: Number(e.target.value) / 100,
                      })
                    }
                  />
                </div>
                <div className="field" style={{ minWidth: 200 }}>
                  <label><JargonTerm term="CAT" /> group</label>
                  <select
                    value={newBequest.from_person_id === person.id ? (newBequest.cat_group ?? "A") : "A"}
                    onChange={(e) =>
                      setNewBequest({
                        ...newBequest,
                        from_person_id: person.id,
                        cat_group: e.target.value as CatGroup,
                      })
                    }
                  >
                    {CAT_GROUP_OPTIONS.map((g) => (
                      <option key={g} value={g}>
                        {CAT_GROUP_LABELS[g]}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  className="btn"
                  style={{ alignSelf: "flex-end", marginBottom: 1 }}
                  disabled={createBequest.isPending}
                  onClick={() => {
                    if (newBequest.from_person_id !== person.id) {
                      setNewBequest({ ...newBequest, from_person_id: person.id });
                    }
                    onAdd();
                  }}
                >
                  Add
                </button>
              </div>
            </details>
          </div>
        );
      })}

      {people.length === 0 && (
        <div className="card">
          <EmptyState
            title="Set up your household before modelling inheritance."
            hint={
              <>
                <JargonTerm term="CAT">Capital Acquisitions Tax</JargonTerm> depends on who inherits
                from whom and which threshold group they fall under.{" "}
                <a href={`/plans/${planId}/people`}>Go to People →</a>
              </>
            }
          />
        </div>
      )}

      <EditModal
        open={editingId !== null}
        onClose={() => {
          setEditingId(null);
          setEditDraft({});
        }}
        title="Edit bequest"
        footer={
          <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
            <button
              className="btn btn-secondary"
              onClick={() => {
                setEditingId(null);
                setEditDraft({});
              }}
              type="button"
            >
              Cancel
            </button>
            <button className="btn" onClick={onSaveEdit} disabled={updateBequest.isPending}>
              Save
            </button>
          </div>
        }
      >
        {editingId !== null && (() => {
          const editing = bequests.find((b) => b.id === editingId);
          if (!editing) return null;
          const fromPerson = people.find((p) => p.id === editing.from_person_id);
          return (
            <div>
              <p className="muted" style={{ margin: "0 0 12px" }}>
                From <strong>{fromPerson?.name ?? "—"}</strong>
              </p>
              <div className="field">
                <label>To</label>
                <select
                  value={editDraft.to_person_id ?? ""}
                  onChange={(e) =>
                    setEditDraft((d) => ({
                      ...d,
                      to_person_id: e.target.value === "" ? null : Number(e.target.value),
                    }))
                  }
                >
                  <option value="">External</option>
                  {people
                    .filter((p) => p.id !== editing.from_person_id)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                </select>
              </div>
              <div className="field">
                <label>Share %</label>
                <input
                  type="number"
                  inputMode="decimal"
                  min={0}
                  max={100}
                  step={1}
                  value={(editDraft.share_pct ?? editing.share_pct) * 100}
                  onChange={(e) =>
                    setEditDraft((d) => ({ ...d, share_pct: Number(e.target.value) / 100 }))
                  }
                />
              </div>
              <div className="field">
                <label>
                  <JargonTerm term="CAT" /> group
                </label>
                <select
                  value={editDraft.cat_group ?? editing.cat_group}
                  onChange={(e) =>
                    setEditDraft((d) => ({
                      ...d,
                      cat_group: e.target.value as CatGroup,
                    }))
                  }
                >
                  {CAT_GROUP_OPTIONS.map((g) => (
                    <option key={g} value={g}>
                      {CAT_GROUP_LABELS[g]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Notes</label>
                <input
                  type="text"
                  value={editDraft.notes ?? (editing.notes || "")}
                  onChange={(e) =>
                    setEditDraft((d) => ({ ...d, notes: e.target.value || null }))
                  }
                />
              </div>
            </div>
          );
        })()}
      </EditModal>
    </div>
  );
}
