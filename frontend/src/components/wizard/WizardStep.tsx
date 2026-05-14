import type { ReactNode } from "react";

export interface WizardStepProps {
  title: string;
  subtitle?: string;
  stepIndex: number;
  totalSteps: number;
  canAdvance: boolean;
  onNext: () => void;
  onBack?: () => void;
  nextLabel?: string;
  backLabel?: string;
  isFinalStep?: boolean;
  isSubmitting?: boolean;
  errorBanner?: string | null;
  mobileSafeArea?: boolean;
  children: ReactNode;
}

export function WizardStep({
  title,
  subtitle,
  stepIndex,
  totalSteps,
  canAdvance,
  onNext,
  onBack,
  nextLabel,
  backLabel = "Back",
  isFinalStep = false,
  isSubmitting = false,
  errorBanner,
  mobileSafeArea = true,
  children,
}: WizardStepProps) {
  const nextLabelResolved = nextLabel ?? (isFinalStep ? "Finish" : "Continue");
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "calc(100vh - 32px)",
        maxWidth: 720,
        margin: "0 auto",
      }}
    >
      <header
        style={{
          position: "sticky",
          top: 0,
          background: "white",
          padding: "12px 0 8px",
          borderBottom: "1px solid #e2e8f0",
          zIndex: 5,
        }}
      >
        <div className="muted" style={{ fontSize: 12, color: "#64748b" }}>
          Step {stepIndex} of {totalSteps}
        </div>
        <h2 style={{ margin: "4px 0 0", fontSize: 22 }}>{title}</h2>
        {subtitle && (
          <p style={{ margin: "4px 0 0", color: "#475569", fontSize: 14 }}>{subtitle}</p>
        )}
        <div
          aria-hidden="true"
          style={{
            marginTop: 10,
            height: 4,
            background: "#e2e8f0",
            borderRadius: 2,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${(stepIndex / totalSteps) * 100}%`,
              height: "100%",
              background: "#2563eb",
              transition: "width 200ms ease-out",
            }}
          />
        </div>
      </header>

      <div style={{ flex: 1, padding: "16px 0" }}>
        {errorBanner && (
          <div
            role="alert"
            style={{
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#991b1b",
              padding: "10px 12px",
              borderRadius: 6,
              marginBottom: 12,
              fontSize: 14,
            }}
          >
            {errorBanner}
          </div>
        )}
        {children}
      </div>

      <footer
        style={{
          position: "sticky",
          bottom: 0,
          background: "white",
          borderTop: "1px solid #e2e8f0",
          padding: mobileSafeArea
            ? "12px 0 calc(12px + env(safe-area-inset-bottom))"
            : "12px 0",
          display: "flex",
          gap: 8,
          justifyContent: "space-between",
          zIndex: 5,
        }}
      >
        {onBack ? (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onBack}
            disabled={isSubmitting}
            style={{ minHeight: 44, minWidth: 100 }}
          >
            {backLabel}
          </button>
        ) : (
          <span />
        )}
        <button
          type="button"
          className="btn"
          onClick={onNext}
          disabled={!canAdvance || isSubmitting}
          style={{ minHeight: 44, minWidth: 120 }}
        >
          {isSubmitting ? "Working…" : nextLabelResolved}
        </button>
      </footer>
    </div>
  );
}
