import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Route, Routes, useParams } from "react-router-dom";
import { useIsMutating } from "@tanstack/react-query";

import {
  useAssets,
  usePeople,
  usePlan,
  useProjection,
  useUpdatePlan,
} from "../api/hooks";
import { PeoplePane } from "./panes/PeoplePane";
import { AssumptionsPane } from "./panes/AssumptionsPane";
import { IncomePane } from "./panes/IncomePane";
import { ExpensesPane } from "./panes/ExpensesPane";
import { AssetsPane } from "./panes/AssetsPane";
import { LiabilitiesPane } from "./panes/LiabilitiesPane";
import { GoalsPane } from "./panes/GoalsPane";
import { TimelinePane } from "./panes/TimelinePane";
import { LetsSeePane } from "./panes/LetsSeePane";
import { ScenariosPane } from "./panes/ScenariosPane";
import { ComparePane } from "./panes/ComparePane";
import { LegacyPane } from "./panes/LegacyPane";
import { SharingPane } from "./panes/SharingPane";
import { TaxRulesPane } from "./panes/TaxRulesPane";

export function PlanEditorPage() {
  const { planId } = useParams();
  const id = Number(planId);
  const { data: plan, isLoading, error } = usePlan(id);
  const updatePlan = useUpdatePlan(id);

  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [draftBaseYear, setDraftBaseYear] = useState(0);
  const [draftYears, setDraftYears] = useState(0);

  if (isLoading) return <p className="muted">Loading…</p>;
  if (error || !plan)
    return (
      <p style={{ color: "#dc2626" }}>
        Couldn't load plan. <Link to="/plans">Back to plans</Link>
      </p>
    );

  const startEdit = () => {
    setDraftName(plan.name);
    setDraftBaseYear(plan.base_year);
    setDraftYears(plan.projection_years);
    setEditing(true);
  };

  const saveEdit = async () => {
    const years = Math.max(1, Math.min(100, draftYears));
    const baseYear = Math.max(1900, Math.min(2100, draftBaseYear));
    await updatePlan.mutateAsync({
      name: draftName.trim() || plan.name,
      base_year: baseYear,
      projection_years: years,
    });
    setEditing(false);
  };

  return (
    <div>
      <p className="muted" style={{ marginBottom: 4 }}>
        <Link to="/plans">← All plans</Link>
      </p>

      {editing ? (
        <div className="row" style={{ alignItems: "flex-end", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
          <div className="field" style={{ margin: 0 }}>
            <label style={{ fontSize: 12 }}>Plan name</label>
            <input
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              style={{ fontSize: 18, fontWeight: 600, padding: "4px 8px" }}
              autoFocus
              onKeyDown={(e) => { if (e.key === "Enter") saveEdit(); if (e.key === "Escape") setEditing(false); }}
            />
          </div>
          <div className="field" style={{ margin: 0, minWidth: 100 }}>
            <label style={{ fontSize: 12 }}>Base year</label>
            <input
              type="number"
              value={draftBaseYear}
              onChange={(e) => setDraftBaseYear(Number(e.target.value))}
              style={{ padding: "4px 8px" }}
            />
          </div>
          <div className="field" style={{ margin: 0, minWidth: 120 }}>
            <label style={{ fontSize: 12 }}>Horizon (years)</label>
            <input
              type="number"
              min={1}
              max={100}
              value={draftYears}
              onChange={(e) => setDraftYears(Number(e.target.value))}
              style={{ padding: "4px 8px" }}
            />
          </div>
          <button className="btn" onClick={saveEdit} disabled={updatePlan.isPending}>
            {updatePlan.isPending ? "Saving…" : "Save"}
          </button>
          <button className="btn btn-secondary" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </div>
      ) : (
        <div className="row" style={{ alignItems: "baseline", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0 }}>{plan.name}</h2>
          <span className="muted" style={{ fontSize: 14 }}>
            Base year {plan.base_year} · {plan.projection_years} year horizon
          </span>
          <SaveIndicator planId={id} />
          <button
            className="btn btn-secondary"
            onClick={startEdit}
            style={{ fontSize: 12, padding: "2px 10px" }}
          >
            Edit
          </button>
        </div>
      )}

      <FirstRunStepper planId={id} />

      <TabNav planId={id} />


      <Routes>
        <Route index element={<LetsSeePane planId={id} />} />
        <Route path="timeline" element={<TimelinePane planId={id} />} />
        <Route path="people" element={<PeoplePane planId={id} />} />
        <Route path="income" element={<IncomePane planId={id} />} />
        <Route path="expenses" element={<ExpensesPane planId={id} />} />
        <Route path="assets" element={<AssetsPane planId={id} />} />
        <Route path="liabilities" element={<LiabilitiesPane planId={id} />} />
        <Route path="goals" element={<GoalsPane planId={id} />} />
        <Route path="scenarios" element={<ScenariosPane planId={id} />} />
        <Route path="compare" element={<ComparePane planId={id} />} />
        <Route path="assumptions" element={<AssumptionsPane planId={id} />} />
        <Route path="tax-rules" element={<TaxRulesPane planId={id} />} />
        <Route path="legacy" element={<LegacyPane planId={id} />} />
        <Route path="sharing" element={<SharingPane planId={id} />} />
      </Routes>
    </div>
  );
}

function FirstRunStepper({ planId }: { planId: number }) {
  const { data: people } = usePeople(planId);
  const { data: assets } = useAssets(planId);
  const { data: projection } = useProjection(planId);

  const hasPeople = (people?.length ?? 0) > 0;
  const hasAssets = (assets?.length ?? 0) > 0;
  const hasIncome = (projection?.years[0]?.gross_income_total ?? 0) > 0;

  // Dismiss once all three are present — engaged users don't need the nudge.
  if (hasPeople && hasAssets && hasIncome) return null;

  const steps = [
    { label: "Add people", path: `/plans/${planId}/people`, done: hasPeople },
    { label: "Add income", path: `/plans/${planId}/income`, done: hasIncome },
    { label: "Add assets", path: `/plans/${planId}/assets`, done: hasAssets },
    { label: "See projection", path: `/plans/${planId}`, done: false },
  ];

  return (
    <div
      style={{
        background: "#f1f5f9",
        border: "1px solid #e2e8f0",
        borderRadius: 8,
        padding: "10px 14px",
        marginBottom: 12,
      }}
    >
      <div style={{ fontSize: 13, color: "#475569", marginBottom: 8 }}>
        <strong>Getting started.</strong> Add the basics to see your projection.
      </div>
      <ol
        style={{
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
          listStyle: "none",
          padding: 0,
          margin: 0,
        }}
      >
        {steps.map((s, i) => (
          <li key={s.label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <NavLink
              to={s.path}
              end={s.path === `/plans/${planId}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 10px",
                borderRadius: 999,
                background: s.done ? "#dcfce7" : "white",
                color: s.done ? "#166534" : "#1e293b",
                border: `1px solid ${s.done ? "#86efac" : "#cbd5e1"}`,
                textDecoration: "none",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              <span
                aria-hidden
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 18,
                  height: 18,
                  borderRadius: "50%",
                  background: s.done ? "#22c55e" : "#cbd5e1",
                  color: "white",
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                {s.done ? "✓" : i + 1}
              </span>
              {s.label}
            </NavLink>
            {i < steps.length - 1 && <span style={{ color: "#94a3b8" }}>→</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

const ADVANCED_KEY = "meridian:planEditor:advanced";

function TabNav({ planId }: { planId: number }) {
  const [advanced, setAdvanced] = useState<boolean>(() => {
    try {
      return localStorage.getItem(ADVANCED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const toggle = () => {
    setAdvanced((v) => {
      const next = !v;
      try {
        localStorage.setItem(ADVANCED_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  };
  return (
    <nav
      className="row"
      style={{
        borderBottom: "1px solid #e2e8f0",
        marginBottom: 16,
        gap: 0,
        flexWrap: "wrap",
        alignItems: "center",
      }}
    >
      <TabLink to={`/plans/${planId}`} end>
        Let's See
      </TabLink>
      <TabLink to={`/plans/${planId}/timeline`}>Timeline</TabLink>
      <TabLink to={`/plans/${planId}/people`}>People</TabLink>
      <TabLink to={`/plans/${planId}/income`}>Income</TabLink>
      <TabLink to={`/plans/${planId}/expenses`}>Expenses</TabLink>
      <TabLink to={`/plans/${planId}/assets`}>Assets</TabLink>
      <TabLink to={`/plans/${planId}/liabilities`}>Liabilities</TabLink>
      <TabLink to={`/plans/${planId}/goals`}>Goals</TabLink>
      <TabLink to={`/plans/${planId}/scenarios`}>Scenarios</TabLink>
      <TabLink to={`/plans/${planId}/compare`}>Compare</TabLink>
      <TabLink to={`/plans/${planId}/legacy`}>Legacy</TabLink>
      <TabLink to={`/plans/${planId}/sharing`}>Sharing</TabLink>
      {advanced && (
        <>
          <TabLink to={`/plans/${planId}/assumptions`}>Assumptions</TabLink>
          <TabLink to={`/plans/${planId}/tax-rules`}>Tax rules</TabLink>
        </>
      )}
      <button
        type="button"
        onClick={toggle}
        title="Toggle advanced tabs (assumptions, tax-rule editor)"
        style={{
          marginLeft: "auto",
          marginBottom: -1,
          padding: "10px 16px",
          background: "transparent",
          border: "none",
          color: advanced ? "#2563eb" : "#94a3b8",
          fontSize: 12,
          fontWeight: 500,
          cursor: "pointer",
        }}
      >
        {advanced ? "Hide advanced" : "Show advanced"}
      </button>
    </nav>
  );
}

function SaveIndicator({ planId }: { planId: number }) {
  const pending = useIsMutating({ mutationKey: ["plan", planId] });
  const [recentlySaved, setRecentlySaved] = useState(false);
  const wasPending = useRef(0);
  useEffect(() => {
    if (wasPending.current > 0 && pending === 0) {
      setRecentlySaved(true);
      const t = setTimeout(() => setRecentlySaved(false), 1500);
      return () => clearTimeout(t);
    }
    wasPending.current = pending;
  }, [pending]);

  if (pending > 0) {
    return (
      <span
        style={{
          background: "#fef3c7",
          color: "#92400e",
          padding: "2px 8px",
          borderRadius: 999,
          fontSize: 11,
          fontWeight: 600,
        }}
      >
        Saving…
      </span>
    );
  }
  if (recentlySaved) {
    return (
      <span
        style={{
          background: "#dcfce7",
          color: "#166534",
          padding: "2px 8px",
          borderRadius: 999,
          fontSize: 11,
          fontWeight: 600,
        }}
      >
        ✓ Saved
      </span>
    );
  }
  return null;
}

function TabLink({
  to,
  end,
  children,
}: {
  to: string;
  end?: boolean;
  children: React.ReactNode;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      style={({ isActive }) => ({
        padding: "10px 16px",
        marginBottom: -1,
        borderBottom: isActive ? "2px solid #2563eb" : "2px solid transparent",
        color: isActive ? "#2563eb" : "#475569",
        textDecoration: "none",
        fontWeight: 500,
      })}
    >
      {children}
    </NavLink>
  );
}
