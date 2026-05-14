import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { emitToast } from "../components/Toast";
import { confirmDialog } from "../components/ConfirmDialog";
import { WizardStep } from "../components/wizard/WizardStep";
import { PlanStep } from "../components/wizard/steps/PlanStep";
import { PeopleStep } from "../components/wizard/steps/PeopleStep";
import { IncomeStep } from "../components/wizard/steps/IncomeStep";
import { AssetsStep } from "../components/wizard/steps/AssetsStep";
import { PropertiesStep } from "../components/wizard/steps/PropertiesStep";
import { LiabilitiesStep } from "../components/wizard/steps/LiabilitiesStep";
import { GoalsStep } from "../components/wizard/steps/GoalsStep";
import { ReviewStep } from "../components/wizard/steps/ReviewStep";
import { useWizard, WIZARD_STEPS, type WizardStepId } from "../wizard/store";
import { canAdvance } from "../wizard/validation";
import { submitWizard, type SubmitProgress, type SubmitResult } from "../wizard/submit";

const STEP_META: Record<WizardStepId, { title: string; subtitle?: string }> = {
  plan: { title: "Your plan", subtitle: "Name and time horizon" },
  people: { title: "People", subtitle: "Plan holder and any partner" },
  income: { title: "Income", subtitle: "Salaries, pensions, and bonuses" },
  assets: { title: "Assets", subtitle: "Cash, deposits, investments, and pensions" },
  properties: { title: "Properties", subtitle: "Homes and buy-to-lets" },
  liabilities: { title: "Liabilities", subtitle: "Mortgages and loans" },
  goals: { title: "Goals", subtitle: "What you want the projection to grade" },
  review: { title: "Review", subtitle: "Check and submit" },
};

const USER_FACING_TOTAL = WIZARD_STEPS.length - 1; // exclude review from the "Step X of N" counter

function indexOf(step: WizardStepId): number {
  return WIZARD_STEPS.indexOf(step);
}

export function PlanWizardPage() {
  const { stepId } = useParams<{ stepId?: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const state = useWizard();
  const reset = useWizard((s) => s.reset);

  const step: WizardStepId = (stepId as WizardStepId) ?? state.currentStep ?? "plan";
  const stepIdx = indexOf(step);

  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState<SubmitProgress | null>(null);
  const [submitResult, setSubmitResult] = useState<SubmitResult | null>(null);

  useEffect(() => {
    if (!WIZARD_STEPS.includes(step)) {
      navigate("/plans/new/plan", { replace: true });
      return;
    }
    useWizard.setState({ currentStep: step });
  }, [step, navigate]);

  const go = (s: WizardStepId) => navigate(`/plans/new/${s}`);
  const onBack = stepIdx > 0 ? () => go(WIZARD_STEPS[stepIdx - 1]) : undefined;
  const onNextStep = () => {
    if (stepIdx < WIZARD_STEPS.length - 1) go(WIZARD_STEPS[stepIdx + 1]);
  };

  const onFinish = async () => {
    setSubmitting(true);
    try {
      const result = await submitWizard(state, submitResult, (p) => setProgress(p));
      setSubmitResult(result);
      if (result.planId != null && result.errors.length === 0) {
        qc.invalidateQueries({ queryKey: ["plans"] });
        emitToast({ kind: "success", message: "Plan created" });
        reset();
        navigate(`/plans/${result.planId}`);
      } else if (result.errors.length > 0) {
        emitToast({
          kind: "error",
          message: `${result.errors.length} item(s) failed. Review and retry.`,
        });
      }
    } catch (e) {
      emitToast({ kind: "error", message: `Submit failed: ${e}` });
    } finally {
      setSubmitting(false);
    }
  };

  const onDiscard = async () => {
    const ok = await confirmDialog({
      title: "Discard wizard?",
      message: "Your draft will be cleared. This cannot be undone.",
      confirmLabel: "Discard",
      danger: true,
    });
    if (ok) {
      reset();
      navigate("/plans");
    }
  };

  const meta = STEP_META[step];
  const isReview = step === "review";
  const userFacingIndex = isReview ? USER_FACING_TOTAL : stepIdx + 1;

  const allowed = canAdvance(step, state);
  const errorBanner =
    submitResult && submitResult.errors.length > 0
      ? `${submitResult.errors.length} item(s) failed to submit. Click Retry below.`
      : null;

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <h1 style={{ margin: 0, fontSize: 18 }}>New plan</h1>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onDiscard}
          style={{ minHeight: 36 }}
        >
          Discard draft
        </button>
      </div>

      <WizardStep
        title={meta.title}
        subtitle={meta.subtitle}
        stepIndex={userFacingIndex}
        totalSteps={USER_FACING_TOTAL}
        canAdvance={allowed}
        onNext={isReview ? onFinish : onNextStep}
        onBack={onBack}
        isFinalStep={isReview}
        isSubmitting={submitting}
        errorBanner={errorBanner}
        nextLabel={
          isReview
            ? submitResult && submitResult.errors.length > 0
              ? "Retry failed items"
              : "Finish"
            : undefined
        }
      >
        {step === "plan" && <PlanStep />}
        {step === "people" && <PeopleStep />}
        {step === "income" && <IncomeStep />}
        {step === "assets" && <AssetsStep />}
        {step === "properties" && <PropertiesStep />}
        {step === "liabilities" && <LiabilitiesStep />}
        {step === "goals" && <GoalsStep />}
        {step === "review" && <ReviewStep progress={progress} />}
      </WizardStep>
    </div>
  );
}
