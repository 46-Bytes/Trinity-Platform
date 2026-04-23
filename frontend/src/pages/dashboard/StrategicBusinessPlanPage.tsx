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
import { AlertCircle, ArrowLeft, CheckCircle2, ClipboardList, Loader2, Plus } from 'lucide-react';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

type LaunchState = 'checking' | 'choose' | 'ready';

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

  const statePlanId = (location.state as { sbpPlanId?: string } | null)?.sbpPlanId;

  const [currentStep, setCurrentStep] = useState(1);
  const lastLoadedId = useRef<string | null>(null);

  const [launchState, setLaunchState] = useState<LaunchState>(
    !engagementId && !statePlanId ? 'checking' : 'ready'
  );
  const [existingPlan, setExistingPlan] = useState<{ id: string; status?: string } | null>(null);

  // Load plan from navigation state, or fall back to fetching by engagement ID
  useEffect(() => {
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
  }, [statePlanId, engagementId, dispatch]);

  // Standalone pre-flight: check for an existing plan session
  useEffect(() => {
    if (launchState !== 'checking') return;
    const token = localStorage.getItem('auth_token');
    if (!token) { setLaunchState('ready'); return; }
    fetch(`${API_BASE_URL}/api/strategic-business-plan/`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: 'include',
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((plans: Array<{ id: string; status?: string }>) => {
        if (plans.length > 0) {
          setExistingPlan(plans[0]);
          setLaunchState('choose');
        } else {
          setLaunchState('ready');
        }
      })
      .catch(() => setLaunchState('ready'));
  }, [launchState]);

  const handleLaunchContinue = () => {
    if (existingPlan) {
      dispatch(clearPlan());
      dispatch(getPlan(existingPlan.id));
      setLaunchState('ready');
    }
  };

  const handleLaunchStartNew = () => {
    dispatch(clearPlan());
    setLaunchState('ready');
  };

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

  if (launchState === 'checking') {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (launchState === 'choose') {
    const statusLabel = existingPlan?.status
      ? existingPlan.status.charAt(0).toUpperCase() + existingPlan.status.slice(1).replace(/_/g, ' ')
      : 'In Progress';
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-3 w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center">
              <ClipboardList className="w-6 h-6 text-accent" />
            </div>
            <CardTitle>Strategic Business Plan</CardTitle>
            <CardDescription>
              You have an existing plan (Status: {statusLabel}).
              Would you like to continue or start fresh?
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button onClick={handleLaunchContinue} className="w-full">
              Continue Existing
            </Button>
            <Button variant="outline" onClick={handleLaunchStartNew} className="w-full">
              <Plus className="w-4 h-4 mr-2" />
              Start New
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate(engagementId ? `/dashboard/engagements/${engagementId}` : '/dashboard/ai-tools')}
        className="flex items-center gap-2"
      >
        <ArrowLeft className="h-4 w-4" />
        {engagementId ? 'Back to Engagement' : 'Back to AI Tools'}
      </Button>

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
