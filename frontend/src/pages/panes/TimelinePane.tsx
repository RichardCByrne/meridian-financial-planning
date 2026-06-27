import { useState } from "react";

import {
  useGoals,
  usePeople,
  usePlan,
  useUpdateGoal,
  useUpdatePerson,
} from "../../api/hooks";
import type { GoalKind } from "../../api/types";
import { NumericInput } from "../../components/NumericInput";

const GOAL_COLORS: Record<GoalKind, string> = {
  retirement: "#7c3aed",
  spend: "#2563eb",
  net_worth: "#f59e0b",
};

const RETIREMENT_COLOR = "#0f172a";

type DragState = {
  kind: "goal" | "person";
  id: number;
  startX: number;
  startYear: number;
  currentYear: number;
};

export function TimelinePane({ planId }: { planId: number }) {
  const { data: plan } = usePlan(planId);
  const { data: people } = usePeople(planId);
  const { data: goals } = useGoals(planId);
  const updateGoal = useUpdateGoal(planId);
  const updatePerson = useUpdatePerson(planId);

  const [drag, setDrag] = useState<DragState | null>(null);
  const [editing, setEditing] = useState<{ kind: "goal" | "person"; id: number; year: number } | null>(null);

  if (!plan) return <p className="muted">Loading…</p>;

  const baseYear = plan.base_year;
  const lastYear = plan.base_year + plan.projection_years - 1;
  const totalYears = plan.projection_years;

  const yearToPct = (year: number) => {
    const clamped = Math.max(baseYear, Math.min(lastYear, year));
    return ((clamped - baseYear) / Math.max(1, totalYears - 1)) * 100;
  };

  const xToYear = (clientX: number, trackEl: HTMLElement): number => {
    const rect = trackEl.getBoundingClientRect();
    const ratio = (clientX - rect.left) / rect.width;
    const year = Math.round(baseYear + ratio * (totalYears - 1));
    return Math.max(baseYear, Math.min(lastYear, year));
  };

  const onPointerDown = (
    e: React.PointerEvent,
    kind: "goal" | "person",
    id: number,
    startYear: number,
  ) => {
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    setDrag({ kind, id, startX: e.clientX, startYear, currentYear: startYear });
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag) return;
    const newYear = xToYear(e.clientX, e.currentTarget as HTMLElement);
    if (newYear !== drag.currentYear) {
      setDrag({ ...drag, currentYear: newYear });
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    if (!drag) return;
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    const finalYear = drag.currentYear;
    if (finalYear !== drag.startYear) {
      if (drag.kind === "goal") {
        updateGoal.mutate({ id: drag.id, body: { target_year: finalYear } });
      } else {
        const person = people?.find((p) => p.id === drag.id);
        if (person) {
          const dobYear = new Date(person.dob).getFullYear();
          const newRetirementAge = finalYear - dobYear;
          if (newRetirementAge >= 40 && newRetirementAge <= 85) {
            updatePerson.mutate({
              id: drag.id,
              body: { retirement_age: newRetirementAge },
            });
          }
        }
      }
    }
    setDrag(null);
  };

  // Decade tick marks for the axis.
  const ticks: number[] = [];
  for (let y = baseYear; y <= lastYear; y++) {
    if (y % 5 === 0 || y === baseYear || y === lastYear) ticks.push(y);
  }

  const personRetirementYear = (personId: number): number | null => {
    const p = people?.find((pp) => pp.id === personId);
    if (!p || p.retirement_age == null) return null;
    return new Date(p.dob).getFullYear() + p.retirement_age;
  };

  return (
    <div>
      <div className="card timeline-card">
        <h3 style={{ marginTop: 0 }}>Timeline</h3>
        <p className="muted">
          Drag pills to change <strong>retirement age</strong> or a goal's <strong>target year</strong>.
          Or tap <strong>Edit</strong> beside any pill to type the year directly (handy on touch).
          Releases trigger a save and the projection refreshes automatically.
        </p>

        <div style={{ marginTop: 24 }}>
          {/* Person retirement lane */}
          {people?.map((p) => {
            const ry = personRetirementYear(p.id);
            if (ry == null) return null;
            const isDragging = drag?.kind === "person" && drag.id === p.id;
            const showYear = isDragging ? drag.currentYear : ry;
            const isEditing = editing?.kind === "person" && editing.id === p.id;
            return (
              <Lane key={`p-${p.id}`} label={`${p.name} retires`}>
                <div
                  className="timeline-track"
                  onPointerMove={onPointerMove}
                  onPointerUp={onPointerUp}
                >
                  <Axis baseYear={baseYear} lastYear={lastYear} ticks={ticks} />
                  <Pill
                    pct={yearToPct(showYear)}
                    color={RETIREMENT_COLOR}
                    label={`Age ${showYear - new Date(p.dob).getFullYear()} · ${showYear}`}
                    onPointerDown={(e) => onPointerDown(e, "person", p.id, ry)}
                    dragging={isDragging}
                  />
                </div>
                <YearTapEdit
                  active={isEditing}
                  currentYear={ry}
                  baseYear={baseYear}
                  lastYear={lastYear}
                  onOpen={() => setEditing({ kind: "person", id: p.id, year: ry })}
                  onCancel={() => setEditing(null)}
                  onCommit={(year) => {
                    const dobYear = new Date(p.dob).getFullYear();
                    const newAge = year - dobYear;
                    if (newAge >= 40 && newAge <= 85) {
                      updatePerson.mutate({ id: p.id, body: { retirement_age: newAge } });
                    }
                    setEditing(null);
                  }}
                />
              </Lane>
            );
          })}

          {/* One lane per goal */}
          {goals?.map((g) => {
            const isDragging = drag?.kind === "goal" && drag.id === g.id;
            const showYear = isDragging ? drag.currentYear : g.target_year;
            const isEditing = editing?.kind === "goal" && editing.id === g.id;
            return (
              <Lane key={`g-${g.id}`} label={g.name}>
                <div
                  className="timeline-track"
                  onPointerMove={onPointerMove}
                  onPointerUp={onPointerUp}
                >
                  <Axis baseYear={baseYear} lastYear={lastYear} ticks={ticks} />
                  <Pill
                    pct={yearToPct(showYear)}
                    color={GOAL_COLORS[g.kind]}
                    label={`${showYear}`}
                    onPointerDown={(e) => onPointerDown(e, "goal", g.id, g.target_year)}
                    dragging={isDragging}
                  />
                </div>
                <YearTapEdit
                  active={isEditing}
                  currentYear={g.target_year}
                  baseYear={baseYear}
                  lastYear={lastYear}
                  onOpen={() => setEditing({ kind: "goal", id: g.id, year: g.target_year })}
                  onCancel={() => setEditing(null)}
                  onCommit={(year) => {
                    updateGoal.mutate({ id: g.id, body: { target_year: year } });
                    setEditing(null);
                  }}
                />
              </Lane>
            );
          })}

          {(!people || people.length === 0) && (!goals || goals.length === 0) && (
            <p className="muted">
              Add a person with a retirement age or some goals to see them on the timeline.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Lane({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="timeline-lane">
      <div className="timeline-lane-label muted">{label}</div>
      {children}
    </div>
  );
}

function YearTapEdit({
  active,
  currentYear,
  baseYear,
  lastYear,
  onOpen,
  onCancel,
  onCommit,
}: {
  active: boolean;
  currentYear: number;
  baseYear: number;
  lastYear: number;
  onOpen: () => void;
  onCancel: () => void;
  onCommit: (year: number) => void;
}) {
  const [draft, setDraft] = useState<number>(currentYear);
  if (!active) {
    return (
      <button
        type="button"
        className="btn btn-secondary"
        onClick={onOpen}
        style={{ fontSize: 12, padding: "4px 10px", minHeight: 32 }}
      >
        Edit
      </button>
    );
  }
  const clamped = Math.max(baseYear, Math.min(lastYear, draft));
  const outOfRange = draft < baseYear || draft > lastYear;
  return (
    <div className="row" style={{ gap: 4 }}>
      <NumericInput
        integer
        value={draft}
        onChange={(v) => Number.isFinite(v) && setDraft(v)}
        style={{ width: 80, padding: "4px 6px" }}
      />
      <button
        type="button"
        className="btn"
        onClick={() => onCommit(clamped)}
        style={{ fontSize: 12, padding: "4px 10px" }}
        disabled={outOfRange}
      >
        Save
      </button>
      <button
        type="button"
        className="btn btn-secondary"
        onClick={onCancel}
        style={{ fontSize: 12, padding: "4px 10px" }}
      >
        Cancel
      </button>
    </div>
  );
}

function Axis({ baseYear, lastYear, ticks }: { baseYear: number; lastYear: number; ticks: number[] }) {
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: "50%",
          height: 2,
          background: "#cbd5e1",
        }}
      />
      {ticks.map((y) => {
        const pct = ((y - baseYear) / Math.max(1, lastYear - baseYear)) * 100;
        return (
          <div
            key={y}
            style={{
              position: "absolute",
              left: `${pct}%`,
              top: 0,
              bottom: 0,
              transform: "translateX(-50%)",
              fontSize: 10,
              color: "#94a3b8",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "flex-end",
              paddingBottom: 2,
            }}
          >
            <div style={{ width: 1, height: 4, background: "#cbd5e1" }} />
            <span>{y}</span>
          </div>
        );
      })}
    </>
  );
}

function Pill({
  pct,
  color,
  label,
  onPointerDown,
  dragging,
}: {
  pct: number;
  color: string;
  label: string;
  onPointerDown: (e: React.PointerEvent) => void;
  dragging: boolean;
}) {
  return (
    <div
      onPointerDown={onPointerDown}
      style={{
        position: "absolute",
        left: `${pct}%`,
        top: "50%",
        // Anchor the pill within the track instead of always centring on the
        // year: at 0% it left-aligns, at 100% it right-aligns, centred in
        // between. Stops the right-most marker overflowing the track and
        // covering the Edit button. Drag accuracy is unaffected (the year is
        // derived from the pointer's x, not the pill's centre).
        transform: `translate(-${pct}%, -50%) ${dragging ? "scale(1.06)" : "scale(1)"}`,
        background: color,
        color: "white",
        padding: "4px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        whiteSpace: "nowrap",
        cursor: dragging ? "grabbing" : "grab",
        boxShadow: dragging ? "0 4px 10px rgba(0,0,0,0.2)" : "0 1px 3px rgba(0,0,0,0.2)",
        userSelect: "none",
        touchAction: "none",
        zIndex: 1,
      }}
    >
      {label}
    </div>
  );
}
