import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  createMatrix,
  getMatrix,
  clearMatrix,
  updateStepProgress,
} from '@/store/slices/rolesMatrixReducer';
import { InputsStep, ExtractStep, MatrixStep } from '@/components/roles-matrix';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, ArrowLeft, CheckCircle2, Loader2, Plus, Users } from 'lucide-react';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

type LaunchState = 'checking' | 'choose' | 'ready';

const STEPS = [
  { step: 1, label: 'Inputs' },
  { step: 2, label: 'Extract' },
  { step: 3, label: 'Matrix' },
] as const;

export default function RolesMatrixPage() {
  const dispatch = useAppDispatch();
  const location = useLocation();
  const navigate = useNavigate();
  const { engagementId } = useParams<{ engagementId: string }>();
  const {
    currentMatrix,
    isLoading,
    isUploading,
    isExtracting,
    isGenerating,
    isSaving,
    isExporting,
    error,
  } = useAppSelector((state) => state.rolesMatrix);

  const stateMatrixId = (location.state as { matrixId?: string } | null)?.matrixId;

  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const lastLoadedId = useRef<string | null>(null);

  const [launchState, setLaunchState] = useState<LaunchState>(stateMatrixId ? 'ready' : 'checking');
  const [existingMatrix, setExistingMatrix] = useState<{ id: string; status: string } | null>(null);

  // Load the matrix passed through navigation state (from FollowUpToolsTab)
  useEffect(() => {
    if (stateMatrixId && lastLoadedId.current !== stateMatrixId) {
      lastLoadedId.current = stateMatrixId;
      dispatch(getMatrix(stateMatrixId));
    }
  }, [stateMatrixId, dispatch]);

  // Pre-flight: offer to continue an existing matrix
  useEffect(() => {
    if (launchState !== 'checking') return;
    const token = localStorage.getItem('auth_token');
    if (!token) {
      setLaunchState('ready');
      return;
    }
    const query = engagementId ? `?engagement_id=${engagementId}` : '';
    fetch(`${API_BASE_URL}/api/roles-matrix/${query}`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: 'include',
    })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => {
        const matrices: Array<{ id: string; status: string }> = data.matrices || [];
        if (matrices.length > 0) {
          setExistingMatrix(matrices[0]);
          setLaunchState('choose');
        } else {
          setLaunchState('ready');
        }
      })
      .catch(() => setLaunchState('ready'));
  }, [launchState, engagementId]);

  // Create a matrix as soon as the advisor lands on a fresh session
  useEffect(() => {
    if (launchState !== 'ready' || currentMatrix || isLoading || stateMatrixId) return;
    dispatch(createMatrix({ engagementId }))
      .unwrap()
      .then((result) => {
        if (result?.matrix_id) {
          lastLoadedId.current = result.matrix_id;
          dispatch(getMatrix(result.matrix_id));
        }
      })
      .catch(() => {
        // The error is surfaced through the slice
      });
  }, [launchState, currentMatrix, isLoading, stateMatrixId, engagementId, dispatch]);

  // Restore the advisor's position when returning to an existing matrix
  const loadedMatrixId = currentMatrix?.id;
  const savedStep = currentMatrix?.current_step;
  useEffect(() => {
    if (savedStep && savedStep >= 1 && savedStep <= 3) {
      setCurrentStep(savedStep as 1 | 2 | 3);
    }
    // Only restore on load, so in-session step changes are not overridden
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadedMatrixId]);

  const goToStep = (step: 1 | 2 | 3) => {
    setCurrentStep(step);
    if (currentMatrix) {
      dispatch(
        updateStepProgress({
          matrixId: currentMatrix.id,
          currentStep: step,
          maxStepReached: Math.max(step, currentMatrix.max_step_reached || 1),
        })
      );
    }
  };

  const handleLaunchContinue = () => {
    if (existingMatrix) {
      dispatch(clearMatrix());
      lastLoadedId.current = existingMatrix.id;
      dispatch(getMatrix(existingMatrix.id));
      setLaunchState('ready');
    }
  };

  const handleLaunchStartNew = () => {
    dispatch(clearMatrix());
    lastLoadedId.current = null;
    setCurrentStep(1);
    setLaunchState('ready');
  };

  const handleStartOver = () => {
    dispatch(clearMatrix());
    lastLoadedId.current = null;
    setCurrentStep(1);
    toast.info('Starting a new matrix');
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
              <Users className="w-6 h-6 text-accent" />
            </div>
            <CardTitle>Roles &amp; Responsibilities Matrix</CardTitle>
            <CardDescription>
              You have an existing matrix (Status:{' '}
              {(existingMatrix?.status || '').replace(/_/g, ' ')}). Would you like to continue or start
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
        onClick={() => navigate(engagementId ? `/dashboard/engagements/${engagementId}` : '/dashboard/ai-tools')}
        className="flex items-center gap-2"
      >
        <ArrowLeft className="h-4 w-4" />
        {engagementId ? 'Back to Engagement' : 'Back to AI Tools'}
      </Button>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            Roles &amp; Responsibilities Matrix
          </h1>
          <p className="text-muted-foreground mt-2">
            Turn position descriptions and notes into a matrix that matches the HR Planning Tool.
          </p>
        </div>
        {currentMatrix && (
          <Button variant="outline" onClick={handleStartOver}>
            Start New Matrix
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
                    onClick={() => goToStep(step as 1 | 2 | 3)}
                    disabled={step > (currentMatrix?.max_step_reached || 1)}
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
                    <span className={`text-sm truncate ${isActive ? 'font-semibold' : ''}`}>{label}</span>
                  </button>
                  {index < STEPS.length - 1 && <div className="flex-1 h-px bg-border mx-2 sm:mx-4" />}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {!currentMatrix ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {currentStep === 1 && (
            <InputsStep
              matrix={currentMatrix}
              isUploading={isUploading}
              isSaving={isSaving}
              onComplete={() => goToStep(2)}
            />
          )}
          {currentStep === 2 && (
            <ExtractStep
              matrix={currentMatrix}
              isExtracting={isExtracting}
              onComplete={() => goToStep(3)}
              onBack={() => goToStep(1)}
            />
          )}
          {currentStep === 3 && (
            <MatrixStep
              matrix={currentMatrix}
              isGenerating={isGenerating}
              isSaving={isSaving}
              isExporting={isExporting}
              onBack={() => goToStep(2)}
            />
          )}
        </>
      )}
    </div>
  );
}
