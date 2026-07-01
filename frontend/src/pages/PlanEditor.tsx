import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation, useParams } from "react-router-dom";
import { useIsMutating } from "@tanstack/react-query";

import {
  useAssets,
  usePeople,
  usePlan,
  useProjection,
  useUpdatePlan,
} from "../api/hooks";
import { PeoplePane } from "./panes/PeoplePane";
import { ChildrenPane } from "./panes/ChildrenPane";
import { BenefitsPane } from "./panes/BenefitsPane";
import { AssumptionsPane } from "./panes/AssumptionsPane";
import { IncomePane } from "./panes/IncomePane";
import { ExpensesPane } from "./panes/ExpensesPane";
import { AssetsPane } from "./panes/AssetsPane";
import { LiabilitiesPane } from "./panes/LiabilitiesPane";
import { ProtectionPane } from "./panes/ProtectionPane";
import { DBPensionsPane } from "./panes/DBPensionsPane";
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
          <div className="field" style={{ margin: 0, minWidth: 120 }}>
            <label style={{ fontSize: 12 }}>Base year</label>
            <input
              type="number"
              value={draftBaseYear}
              onChange={(e) => setDraftBaseYear(Number(e.target.value))}
              style={{ padding: "4px 8px", minWidth: 100 }}
            />
          </div>
          <div className="field" style={{ margin: 0, minWidth: 140 }}>
            <label style={{ fontSize: 12 }}>Horizon (years)</label>
            <input
              type="number"
              min={1}
              max={100}
              value={draftYears}
              onChange={(e) => setDraftYears(Number(e.target.value))}
              style={{ padding: "4px 8px", minWidth: 100 }}
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
        <Route path="children" element={<ChildrenPane planId={id} />} />
        <Route path="income" element={<IncomePane planId={id} />} />
        <Route path="benefits" element={<BenefitsPane planId={id} />} />
        <Route path="expenses" element={<ExpensesPane planId={id} />} />
        <Route path="assets" element={<AssetsPane planId={id} />} />
        <Route path="liabilities" element={<LiabilitiesPane planId={id} />} />
        <Route path="protection" element={<ProtectionPane planId={id} />} />
        <Route path="db-pensions" element={<DBPensionsPane planId={id} />} />
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
  const { data: plan } = usePlan(planId);
  const { data: people, isLoading: peopleLoading } = usePeople(planId);
  const { data: assets, isLoading: assetsLoading } = useAssets(planId);
  const { data: projection, isLoading: projectionLoading } = useProjection(planId);
  const updatePlan = useUpdatePlan(planId);

  const alreadyComplete = plan?.onboarding_complete ?? false;

  const hasPeople = (people?.length ?? 0) > 0;
  const hasAssets = (assets?.length ?? 0) > 0;
  const hasIncome = (projection?.years[0]?.gross_income_total ?? 0) > 0;
  const allDone = hasPeople && hasAssets && hasIncome;

  // Persist the flag the first time everything is present, so future loads can
  // skip the stepper from a single cached boolean instead of re-deriving it
  // (which caused the brief flash while people/assets/projection were loading).
  const flaggedRef = useRef(false);
  useEffect(() => {
    if (plan && !alreadyComplete && allDone && !flaggedRef.current) {
      flaggedRef.current = true;
      updatePlan.mutate({ onboarding_complete: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan, alreadyComplete, allDone]);

  // Already onboarded → never render (decided from the flag alone, no flash).
  if (alreadyComplete) return null;
  // Wait for the data that judges completion before deciding to show anything;
  // this is what eliminates the flash for plans that are already complete.
  if (!plan || peopleLoading || assetsLoading || projectionLoading) return null;
  // All tasks done but flag not yet persisted — hide now; the effect sets it.
  if (allDone) return null;

  const steps = [
    { label: "Add people", path: `/plans/${planId}/people`, done: hasPeople },
    { label: "Add income", path: `/plans/${planId}/income`, done: hasIncome },
    { label: "Add assets", path: `/plans/${planId}/assets`, done: hasAssets },
    { label: "See projection", path: `/plans/${planId}`, done: false },
  ];
  const doneCount = steps.filter((s) => s.done).length;

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
        <strong>Getting started ({doneCount}/{steps.length}).</strong> Add the basics to see your
        projection.
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
          <li key={s.label}>
            <NavLink
              to={s.path}
              end={s.path === `/plans/${planId}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
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
          </li>
        ))}
      </ol>
    </div>
  );
}

// Plan editor navigation is two-tier: five groups on top, and the active
// group's members as a sub-row beneath. `seg` is the path segment after the
// plan id ("" is the index — the Outlook/Let's See view).
type PlanTab = { label: string; seg: string };
type PlanTabGroup = { id: string; label: string; tabs: PlanTab[] };

const PLAN_TAB_GROUPS: PlanTabGroup[] = [
  {
    id: "outlook",
    label: "Outlook",
    tabs: [
      { label: "Let's See", seg: "" },
      { label: "Timeline", seg: "timeline" },
      { label: "Scenarios", seg: "scenarios" },
      { label: "Compare", seg: "compare" },
    ],
  },
  {
    id: "household",
    label: "Household",
    tabs: [
      { label: "People", seg: "people" },
      { label: "Children", seg: "children" },
      { label: "Benefits", seg: "benefits" },
    ],
  },
  {
    id: "finances",
    label: "Finances",
    tabs: [
      { label: "Income", seg: "income" },
      { label: "Expenses", seg: "expenses" },
      { label: "Assets", seg: "assets" },
      { label: "Liabilities", seg: "liabilities" },
      { label: "Protection", seg: "protection" },
      { label: "DB Pension", seg: "db-pensions" },
    ],
  },
  {
    id: "planning",
    label: "Planning",
    tabs: [
      { label: "Goals", seg: "goals" },
      { label: "Legacy", seg: "legacy" },
    ],
  },
  {
    id: "settings",
    label: "Settings",
    tabs: [
      { label: "Sharing", seg: "sharing" },
      { label: "Assumptions", seg: "assumptions" },
      { label: "Tax rules", seg: "tax-rules" },
    ],
  },
];

function TabNav({ planId }: { planId: number }) {
  const navRef = useRef<HTMLElement | null>(null);
  const location = useLocation();
  const base = `/plans/${planId}`;
  const toPath = (seg: string) => (seg ? `${base}/${seg}` : base);

  // First path segment after the plan id decides the active group.
  const seg = location.pathname.startsWith(base)
    ? location.pathname.slice(base.length).replace(/^\/+/, "").split("/")[0]
    : "";
  const activeGroup =
    PLAN_TAB_GROUPS.find((g) => g.tabs.some((t) => t.seg === seg)) ?? PLAN_TAB_GROUPS[0];

  // Keep the active member tab in view on the (horizontally scrollable) sub-row.
  useLayoutEffect(() => {
    const el = navRef.current?.querySelector<HTMLAnchorElement>("a.active");
    if (el && typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
    }
  }, [location.pathname]);

  return (
    <div className="tabnav-shell">
      <nav className="tabgroups" aria-label="Plan sections">
        {PLAN_TAB_GROUPS.map((g) => (
          <Link
            key={g.id}
            to={toPath(g.tabs[0].seg)}
            className={g.id === activeGroup.id ? "active" : ""}
            aria-current={g.id === activeGroup.id ? "page" : undefined}
          >
            {g.label}
          </Link>
        ))}
      </nav>
      <nav ref={navRef} className="tabnav" aria-label={`${activeGroup.label} tabs`}>
        {activeGroup.tabs.map((t) => (
          <TabLink key={t.seg || "index"} to={toPath(t.seg)} end={t.seg === ""}>
            {t.label}
          </TabLink>
        ))}
      </nav>
    </div>
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
    <NavLink to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>
      {children}
    </NavLink>
  );
}
