import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  createBuild,
  getBuild,
  clearBuild,
  setActiveRole,
  updateStepProgress,
} from '@/store/slices/pdScorecardReducer';
import { InputsStep, RolesStep, PDStep, ScorecardStep } from '@/components/pd-scorecard';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, ArrowLeft, CheckCircle2, FileSignature, Loader2, Plus } from 'lucide-react';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

type LaunchState = 'checking' | 'choose' | 'ready';
type Step = 1 | 2 | 3 | 4;

const STEPS = [
  { step: 1, label: 'Inputs' },
  { step: 2, label: 'Roles' },
  { step: 3, label: 'Position Description' },
  { step: 4, label: 'Scorecard' },
] as const;

export default function PDScorecardPage() {
  const dispatch = useAppDispatch();
  const location = useLocation();
  const navigate = useNavigate();
  const { engagementId } = useParams<{ engagementId: string }>();
  const {
    currentBuild,
    suggestedRoles,
    activeRoleId,
    isLoading,
    isUploading,
    isExtracting,
    isGeneratingPD,
    isGeneratingScorecard,
    isSaving,
    isExporting,
    error,
  } = useAppSelector((state) => state.pdScorecard);

  const stateBuildId = (location.state as { buildId?: string } | null)?.buildId;

  const [currentStep, setCurrentStep] = useState<Step>(1);
  const lastLoadedId = useRef<string | null>(null);

  const [launchState, setLaunchState] = useState<LaunchState>(stateBuildId ? 'ready' : 'checking');
  const [existingBuild, setExistingBuild] = useState<{ id: string; status: string } | null>(null);

  // Load the build passed through navigation state (from FollowUpToolsTab)
  useEffect(() => {
    if (stateBuildId && lastLoadedId.current !== stateBuildId) {
      lastLoadedId.current = stateBuildId;
      dispatch(getBuild(stateBuildId));
    }
  }, [stateBuildId, dispatch]);

  // Pre-flight: offer to continue an existing build
  useEffect(() => {
    if (launchState !== 'checking') return;
    const token = localStorage.getItem('auth_token');
    if (!token) {
      setLaunchState('ready');
      return;
    }
    const query = engagementId ? `?engagement_id=${engagementId}` : '';
    fetch(`${API_BASE_URL}/api/pd-scorecard/${query}`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: 'include',
    })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => {
        const builds: Array<{ id: string; status: string }> = data.builds || [];
        if (builds.length > 0) {
          setExistingBuild(builds[0]);
          setLaunchState('choose');
        } else {
          setLaunchState('ready');
        }
      })
      .catch(() => setLaunchState('ready'));
  }, [launchState, engagementId]);

  // Create a build as soon as the advisor lands on a fresh session
  useEffect(() => {
    if (launchState !== 'ready' || currentBuild || isLoading || stateBuildId) return;
    dispatch(createBuild({ engagementId }))
      .unwrap()
      .then((result) => {
        if (result?.build_id) {
          lastLoadedId.current = result.build_id;
          dispatch(getBuild(result.build_id));
        }
      })
      .catch(() => {
        // The error is surfaced through the slice
      });
  }, [launchState, currentBuild, isLoading, stateBuildId, engagementId, dispatch]);

  // Restore the advisor's position when returning to an existing build
  const loadedBuildId = currentBuild?.id;
  const savedStep = currentBuild?.current_step;
  useEffect(() => {
    if (savedStep && savedStep >= 1 && savedStep <= 4) {
      setCurrentStep(savedStep as Step);
    }
    // Only restore on load, so in-session step changes are not overridden
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadedBuildId]);

  // Default to the first included role so steps 3 and 4 open on something
  const roles = currentBuild?.roles;
  useEffect(() => {
    if (activeRoleId || !roles?.length) return;
    const firstIncluded = roles.find((role) => role.included);
    if (firstIncluded) {
      dispatch(setActiveRole(firstIncluded.id));
    }
  }, [roles, activeRoleId, dispatch]);

  const goToStep = (step: Step) => {
    setCurrentStep(step);
    if (currentBuild) {
      dispatch(
        updateStepProgress({
          buildId: currentBuild.id,
          currentStep: step,
          maxStepReached: Math.max(step, currentBuild.max_step_reached || 1),
        })
      );
    }
  };

  const handleLaunchContinue = () => {
    if (existingBuild) {
      dispatch(clearBuild());
      lastLoadedId.current = existingBuild.id;
      dispatch(getBuild(existingBuild.id));
      setLaunchState('ready');
    }
  };

  const handleLaunchStartNew = () => {
    dispatch(clearBuild());
    lastLoadedId.current = null;
    setCurrentStep(1);
    setLaunchState('ready');
  };

  const handleStartOver = () => {
    dispatch(clearBuild());
    lastLoadedId.current = null;
    setCurrentStep(1);
    toast.info('Starting a new PD & scorecard build');
  };

  if (launchState === 'checking') {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (launchState === 'choose') {
    return (
      <div className="flex items-center justify-center min-h-[60vh] p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-3 w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center">
              <FileSignature className="w-6 h-6 text-accent" />
            </div>
            <CardTitle>PD &amp; Role Scorecards</CardTitle>
            <CardDescription>
              You have an existing build (Status:{' '}
              {(existingBuild?.status || '').replace(/_/g, ' ')}). Would you like to continue or start
              fresh?
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
    <div className="container mx-auto p-4 sm:p-6 space-y-6">
      <Button
        variant="ghost"
        size="sm"
        onClick={() =>
          navigate(engagementId ? `/dashboard/engagements/${engagementId}` : '/dashboard/ai-tools')
        }
        className="flex items-center gap-2"
      >
        <ArrowLeft className="h-4 w-4" />
        {engagementId ? 'Back to Engagement' : 'Back to AI Tools'}
      </Button>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            PD &amp; Role Scorecards
          </h1>
          <p className="text-muted-foreground mt-2">
            Turn a completed roles matrix into a position description and a half-yearly scorecard,
            one role at a time.
          </p>
        </div>
        {currentBuild && (
          <Button variant="outline" onClick={handleStartOver}>
            Start New Build
          </Button>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Stepper */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between gap-2">
            {STEPS.map(({ step, label }, index) => {
              const isDone = currentStep > step;
              const isActive = currentStep === step;
              return (
                <div key={step} className="flex items-center flex-1 last:flex-none min-w-0">
                  <button
                    type="button"
                    onClick={() => goToStep(step as Step)}
                    disabled={step > (currentBuild?.max_step_reached || 1)}
                    className="flex items-center gap-2 min-w-0 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <span
                      className={`flex items-center justify-center w-8 h-8 rounded-full flex-shrink-0 ${
                        isDone
                          ? 'bg-green-500 text-white'
                          : isActive
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      }`}
                    >
                      {isDone ? <CheckCircle2 className="w-5 h-5" /> : step}
                    </span>
                    <span className={`text-sm truncate ${isActive ? 'font-semibold' : ''}`}>
                      {label}
                    </span>
                  </button>
                  {index < STEPS.length - 1 && <div className="flex-1 h-px bg-border mx-2 sm:mx-4" />}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {!currentBuild ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {currentStep === 1 && (
            <InputsStep
              build={currentBuild}
              isUploading={isUploading}
              isSaving={isSaving}
              onComplete={() => goToStep(2)}
            />
          )}
          {currentStep === 2 && (
            <RolesStep
              build={currentBuild}
              suggestedRoles={suggestedRoles}
              isExtracting={isExtracting}
              isSaving={isSaving}
              onBack={() => goToStep(1)}
              onComplete={() => goToStep(3)}
            />
          )}
          {currentStep === 3 && (
            <PDStep
              build={currentBuild}
              activeRoleId={activeRoleId}
              isGenerating={isGeneratingPD}
              isSaving={isSaving}
              isExporting={isExporting}
              onSelectRole={(roleId) => dispatch(setActiveRole(roleId))}
              onBack={() => goToStep(2)}
              onComplete={() => goToStep(4)}
            />
          )}
          {currentStep === 4 && (
            <ScorecardStep
              build={currentBuild}
              activeRoleId={activeRoleId}
              isGenerating={isGeneratingScorecard}
              isSaving={isSaving}
              isExporting={isExporting}
              onSelectRole={(roleId) => dispatch(setActiveRole(roleId))}
              onBack={() => goToStep(3)}
            />
          )}
        </>
      )}
    </div>
  );
}
