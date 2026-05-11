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
const STORAGE_KEY = "meridian:tour:done:v1";

const STEPS: Step[] = [
  {
    title: "Welcome to Meridian",
    body: (
      <p>
        Build a financial plan for your household, watch it project year-by-year through
        Irish tax rules, and pressure-test it with scenarios. This tour walks you through
        the five core panes in under two minutes. You can quit any time.
      </p>
    ),
    navigate: () => "/plans",
  },
  {
    title: "Start with a plan",
    body: (
      <p>
        On the Plans list, hit <strong>Try a sample plan</strong> for a populated household
        (Carla & David — two adults, joint mortgage, pensions, retirement goal), or create
        an empty one and follow along. We'll click into it together.
      </p>
    ),
    navigate: () => "/plans",
  },
  {
    title: "People",
    body: (
      <p>
        Every plan starts with the humans. Each person's date of birth drives ages and
        state-pension eligibility; their retirement age drives the pension lifecycle (lump
        sum + ARF drawdown). Filing status is auto-inferred for the household.
      </p>
    ),
    navigate: (id) => (id ? `/plans/${id}/people` : "/plans"),
  },
  {
    title: "Income",
    body: (
      <p>
        Add salaries, rentals, self-employment, or pensions in payment. Employment income
        triggers PAYE/PRSI/USC. The <strong>Pension %</strong> field is your contribution
        rate — tax relief is applied up to the age-based cap (15–40% by age, capped at
        €115k earnings).
      </p>
    ),
    navigate: (id) => (id ? `/plans/${id}/income` : "/plans"),
  },
  {
    title: "Assets",
    body: (
      <p>
        Cash, ETFs, pension wrappers, property — each has its own tax treatment baked in.
        Pensions use AVCs (age-capped, pre-tax). ETFs use 41% exit tax with deemed
        disposal. Unwrapped investments use 33% CGT. Just pick the kind; the engine
        handles the rest.
      </p>
    ),
    navigate: (id) => (id ? `/plans/${id}/assets` : "/plans"),
  },
  {
    title: "Let's See",
    body: (
      <p>
        Your projection lands here. Hover any year to see the full breakdown. Toggle
        <strong> Today's € (real)</strong> to strip inflation, or <strong>Probability
        bands</strong> for the Monte Carlo fan chart with shortfall probability. Goals show
        as ✅/⚠/⏳ chips below the summary.
      </p>
    ),
    navigate: (id) => (id ? `/plans/${id}` : "/plans"),
  },
  {
    title: "That's it",
    body: (
      <p>
        Build a few scenarios next ("Retire at 60", "Inheritance in 2034") and use Compare
        to see the impact. Open the <strong>Guide</strong> in the sidebar any time for a
        full reference.
      </p>
    ),
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

export function tourCompleted(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function TourOverlay({ onClose }: { onClose: () => void }) {
  const [idx, setIdx] = useState(0);
  const navigate = useNavigate();
  const { data: plans } = usePlans();
  const firstPlanId = plans && plans.length > 0 ? plans[0].id : null;
  const step = STEPS[idx];
  const isLast = idx === STEPS.length - 1;

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
        alignItems: "flex-end",
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
          marginBottom: 24,
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
                background: i <= idx ? "#2563eb" : "#e2e8f0",
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
              onClick={() => {
                if (isLast) onClose();
                else setIdx((i) => i + 1);
              }}
              style={{ fontSize: 13 }}
            >
              {isLast ? "Got it" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
