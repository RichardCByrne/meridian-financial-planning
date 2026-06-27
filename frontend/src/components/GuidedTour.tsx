import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { usePlans } from "../api/hooks";

type Step = {
  title: string;
  body: ReactNode;
  navigate?: (firstPlanId: number | null) => string | null;
};

// Bump version when STEPS content changes meaningfully so returning users see the new tour.
const STORAGE_KEY = "meridian:tour:done:v2";

// This tour deliberately does NOT re-teach data entry — the New plan wizard
// already walks you through People / Income / Assets when you build a plan.
// Here we orient you around what the app *does* with a plan: the projection,
// the timeline, and scenarios — plus where everything lives.
const STEPS: Step[] = [
  {
    title: "Welcome to Meridian",
    body: (
      <p>
        The <strong>New plan</strong> wizard walks you through entering your household. This
        tour is the other half: it shows what Meridian <em>does</em> with that plan — the
        projection, the timeline, and scenarios — in under two minutes. Quit any time.
      </p>
    ),
    navigate: () => "/plans",
  },
  {
    title: "Follow along on a sample plan",
    body: (
      <p>
        On the Plans list, hit <strong>Try a sample plan</strong> for a populated household
        (Carla & David — two adults, joint mortgage, pensions, a retirement goal). We'll
        open it and tour the panes that turn those numbers into a forecast.
      </p>
    ),
    navigate: () => "/plans",
  },
  {
    title: "Let's See — your projection",
    body: (
      <p>
        This is the heart of the app: your plan projected year-by-year through Irish tax
        rules. Hover any year for the full breakdown. Toggle <strong>Today's € (real)</strong>
        to strip out inflation, or <strong>Probability bands</strong> for the Monte Carlo fan
        chart with shortfall probability. Goals show as ✅ / ⚠ / ⏳ chips below the summary.
      </p>
    ),
    navigate: (id) => (id ? `/plans/${id}` : "/plans"),
  },
  {
    title: "Timeline — drag to explore",
    body: (
      <p>
        Drag a person's retirement pill or a goal's target year along the axis and release —
        the projection re-runs instantly. The fastest way to ask "what if I retired two years
        earlier?" without editing any forms.
      </p>
    ),
    navigate: (id) => (id ? `/plans/${id}/timeline` : "/plans"),
  },
  {
    title: "Scenarios & Compare",
    body: (
      <p>
        A scenario is a set of "what if" overrides layered on top of your base plan —
        "Retire at 60", "Inheritance in 2034", a buy-to-let purchase — without touching the
        original. Then <strong>Compare</strong> runs two side-by-side so you can see the
        difference year-by-year.
      </p>
    ),
    navigate: (id) => (id ? `/plans/${id}/scenarios` : "/plans"),
  },
  {
    title: "That's it",
    body: (
      <p>
        Ready to build your own? Hit <strong>New plan</strong> on the Plans list and the
        wizard takes it from there. Open the <strong>Guide</strong> in the sidebar any time
        for a full reference.
      </p>
    ),
    navigate: () => "/plans",
  },
];

type TourContextValue = {
  open: boolean;
  start: () => void;
  close: () => void;
};

const TourContext = createContext<TourContextValue | null>(null);

export function useTour(): TourContextValue {
  const ctx = useContext(TourContext);
  if (!ctx) throw new Error("useTour must be used inside <TourProvider>");
  return ctx;
}

export function TourProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  const start = useCallback(() => setOpen(true), []);
  const close = useCallback(() => {
    setOpen(false);
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(() => ({ open, start, close }), [open, start, close]);

  return (
    <TourContext.Provider value={value}>
      {children}
      {open && <TourOverlay onClose={close} />}
    </TourContext.Provider>
  );
}

function TourOverlay({ onClose }: { onClose: () => void }) {
  const [idx, setIdx] = useState(0);
  const navigate = useNavigate();
  const { data: plans } = usePlans();
  const firstPlanId = plans && plans.length > 0 ? plans[0].id : null;
  const step = STEPS[idx];
  const isLast = idx === STEPS.length - 1;
  // Step 1 ("Start with a plan") gates further pane steps: bodies describe
  // panes only visible inside a plan, so block Next until a plan exists.
  const needsPlanGate = idx === 1 && !firstPlanId;

  useEffect(() => {
    if (step.navigate) {
      const target = step.navigate(firstPlanId);
      if (target) navigate(target);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15, 23, 42, 0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9000,
        padding: 16,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: "white",
          borderRadius: 10,
          padding: "20px 22px",
          maxWidth: 480,
          width: "100%",
          boxShadow: "0 12px 40px rgba(15, 23, 42, 0.25)",
        }}
      >
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <strong style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.05, color: "#64748b" }}>
            Step {idx + 1} of {STEPS.length}
          </strong>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "#64748b",
              fontSize: 18,
              cursor: "pointer",
              padding: 0,
            }}
            aria-label="Close tour"
          >
            ×
          </button>
        </div>
        <h3 style={{ margin: "8px 0 6px 0" }}>{step.title}</h3>
        <div style={{ fontSize: 14, color: "#334155", lineHeight: 1.5 }}>{step.body}</div>
        {needsPlanGate && (
          <p
            style={{
              fontSize: 13,
              color: "#92400e",
              background: "#fef3c7",
              padding: "8px 10px",
              borderRadius: 6,
              marginTop: 10,
              marginBottom: 0,
            }}
          >
            Create a plan (or hit <strong>Try a sample plan</strong>) to continue — the next steps
            walk through panes inside the plan.
          </p>
        )}
        <div
          style={{
            display: "flex",
            gap: 4,
            marginTop: 14,
            marginBottom: 14,
          }}
        >
          {STEPS.map((_, i) => (
            <span
              key={i}
              style={{
                flex: 1,
                height: 4,
                borderRadius: 2,
                background: i <= idx ? "var(--accent, #0e6e62)" : "var(--line-soft, #e2e8f0)",
              }}
            />
          ))}
        </div>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={idx === 0}
            onClick={() => setIdx((i) => Math.max(0, i - 1))}
            style={{ fontSize: 13 }}
          >
            Back
          </button>
          <div className="row" style={{ gap: 6 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              style={{ fontSize: 13 }}
            >
              Skip tour
            </button>
            <button
              type="button"
              className="btn"
              disabled={needsPlanGate}
              onClick={() => {
                if (isLast) onClose();
                else setIdx((i) => i + 1);
              }}
              style={{ fontSize: 13 }}
              title={needsPlanGate ? "Create a plan first" : undefined}
            >
              {isLast ? "Got it" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
