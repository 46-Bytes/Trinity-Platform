import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { getPlan, updateStepProgress, clearPlan } from '@/store/slices/strategicBusinessPlanReducer';
import { SetupUploadStep } from '@/components/strategic-business-plan/SetupUploadStep';
import { CrossAnalysisStep } from '@/components/strategic-business-plan/CrossAnalysisStep';
import { SectionDraftingStep } from '@/components/strategic-business-plan/SectionDraftingStep';
import { PlanAssemblyStep } from '@/components/strategic-business-plan/PlanAssemblyStep';
import { ExportStep } from '@/components/strategic-business-plan/ExportStep';
import { PresentationStep } from '@/components/strategic-business-plan/PresentationStep';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, ArrowLeft, CheckCircle2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const STEP_LABELS = [
  'Setup & Upload',
  'Cross-Analysis',
  'Section Drafting',
  'Plan Assembly',
  'Export',
  'Presentation',
] as const;

export default function StrategicBusinessPlanPage() {
  const dispatch = useAppDispatch();
  const location = useLocation();
  const navigate = useNavigate();
  const { engagementId } = useParams<{ engagementId: string }>();
  const { currentPlan, isLoading, error } = useAppSelector((s) => s.strategicBusinessPlan);

  const [currentStep, setCurrentStep] = useState(1);
  const lastLoadedId = useRef<string | null>(null);

  // Load plan from navigation state, or fall back to fetching by engagement ID
  useEffect(() => {
    const statePlanId = (location.state as { sbpPlanId?: string } | null)?.sbpPlanId;
    if (statePlanId && lastLoadedId.current !== statePlanId) {
      lastLoadedId.current = statePlanId;
      dispatch(getPlan(statePlanId));
      return;
    }
    // Fallback: no state (page refresh / direct URL) — load latest plan for this engagement
    if (!statePlanId && engagementId && lastLoadedId.current !== `engagement-${engagementId}`) {
      lastLoadedId.current = `engagement-${engagementId}`;
      const token = localStorage.getItem('auth_token');
      if (!token) return;
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      fetch(`${API_BASE_URL}/api/strategic-business-plan/?engagement_id=${engagementId}`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      })
        .then((res) => (res.ok ? res.json() : Promise.reject()))
        .then((plans: Array<{ id: string }>) => {
          if (plans.length > 0) {
            dispatch(getPlan(plans[0].id));
          }
        })
        .catch(() => {/* no existing plan, stay on blank step 1 */});
    }
  }, [location.state, engagementId, dispatch]);

  // Restore step from loaded plan
  useEffect(() => {
    if (currentPlan?.current_step) {
      setCurrentStep(currentPlan.current_step);
    }
  }, [currentPlan?.current_step]);

  const planId = currentPlan?.id || null;
  const maxStep = currentPlan?.max_step_reached || currentStep;

  const goToStep = (step: number) => {
    if (step <= maxStep || step === currentStep + 1) {
      setCurrentStep(step);
      if (planId) {
        dispatch(updateStepProgress({ planId, currentStep: step, maxStepReached: Math.max(step, maxStep) }));
      }
    }
  };

  const handleStepComplete = () => {
    const nextStep = currentStep + 1;
    if (nextStep <= 6) {
      goToStep(nextStep);
      toast.success(`Step ${currentStep} complete!`);
    }
  };

  const handleStartOver = () => {
    dispatch(clearPlan());
    setCurrentStep(1);
    toast.info('Starting new plan session');
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {engagementId && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/dashboard/engagements/${engagementId}`)}
          className="flex items-center gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Engagement
        </Button>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Strategic Business Plan</h1>
          <p className="text-muted-foreground mt-2">
            Build a professional Strategic Business Plan from your strategy workbook and supporting materials
          </p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Progress Steps */}
      <Card>
        <CardHeader>
          <CardTitle>Workflow Steps</CardTitle>
          <CardDescription>Follow these steps to generate your Strategic Business Plan</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            {STEP_LABELS.map((label, i) => {
              const stepNum = i + 1;
              const isDone = currentStep > stepNum;
              const isActive = currentStep === stepNum;
              const isClickable = stepNum <= maxStep;

              return (
                <div key={label} className="flex items-center flex-1">
                  <button
                    onClick={() => isClickable && goToStep(stepNum)}
                    disabled={!isClickable}
                    className="flex items-center space-x-2 disabled:cursor-default"
                  >
                    <div
                      className={`flex items-center justify-center w-8 h-8 rounded-full text-xs font-medium ${
                        isDone
                          ? 'bg-green-500 text-white'
                          : isActive
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {isDone ? (
                        <CheckCircle2 className="w-5 h-5" />
                      ) : isActive && isLoading ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        stepNum
                      )}
                    </div>
                    <span className={`text-xs hidden md:inline ${isActive ? 'font-semibold' : ''}`}>
                      {label}
                    </span>
                  </button>
                  {i < STEP_LABELS.length - 1 && <div className="flex-1 h-px bg-border mx-2" />}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Step Content */}
      {currentStep === 1 && (
        <SetupUploadStep
          planId={planId}
          engagementId={engagementId}
          onComplete={handleStepComplete}
          isLoading={isLoading}
        />
      )}

      {currentStep === 2 && planId && (
        <CrossAnalysisStep planId={planId} onComplete={handleStepComplete} />
      )}

      {currentStep === 3 && planId && (
        <SectionDraftingStep planId={planId} onComplete={handleStepComplete} />
      )}

      {currentStep === 4 && planId && (
        <PlanAssemblyStep planId={planId} onComplete={handleStepComplete} />
      )}

      {currentStep === 5 && planId && (
        <ExportStep planId={planId} onComplete={handleStepComplete} />
      )}

      {currentStep === 6 && planId && (
        <PresentationStep planId={planId} />
      )}
    </div>
  );
}
