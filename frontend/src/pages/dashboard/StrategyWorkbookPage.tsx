import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  uploadDocuments,
  extractData,
  generateWorkbook,
  clearWorkbook,
  setReviewNotes,
  precheckWorkbook,
  getWorkbook,
} from '@/store/slices/strategyWorkbookReducer';
import { UploadStep } from '@/components/strategy-workbook/UploadStep';
import { ClarifyStep } from '@/components/strategy-workbook/ClarifyStep';
import { ExtractStep } from '@/components/strategy-workbook/ExtractStep';
import { GenerateStep } from '@/components/strategy-workbook/GenerateStep';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, ArrowLeft, CheckCircle2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export default function StrategyWorkbookPage() {
  const dispatch = useAppDispatch();
  const location = useLocation();
  const navigate = useNavigate();
  const { engagementId } = useParams<{ engagementId: string }>();
  const { currentWorkbook, isLoading, isExtracting, isGenerating, error, uploadedFiles } = useAppSelector(
    (state) => state.strategyWorkbook
  );

  const [currentStep, setCurrentStep] = useState<'upload' | 'clarify' | 'extract' | 'generate'>('upload');
  const [reviewNotes, setReviewNotes] = useState('');
  const lastLoadedId = useRef<string | null>(null);

  // Load workbook from navigation state (when coming from FollowUpToolsTab)
  useEffect(() => {
    const stateWorkbookId = (location.state as { workbookId?: string } | null)?.workbookId;
    if (stateWorkbookId && lastLoadedId.current !== stateWorkbookId) {
      lastLoadedId.current = stateWorkbookId;
      dispatch(getWorkbook(stateWorkbookId));
    }
  }, [location.state, dispatch]);

  const handleUploadComplete = async () => {
    if (currentWorkbook) {
      toast.success('Documents uploaded successfully!');
      try {
        const result = await dispatch(precheckWorkbook(currentWorkbook.id)).unwrap();
        const hasQuestions =
          Array.isArray(result.clarification_questions) &&
          result.clarification_questions.length > 0;
        if (hasQuestions || result.status === 'needs_clarification') {
          setCurrentStep('clarify');
        } else {
          setCurrentStep('extract');
        }
      } catch (err) {
        // If precheck fails, fall back to extraction
        console.error('Precheck failed, continuing to extraction:', err);
        setCurrentStep('extract');
      }
    }
  };

  const handleClarifyComplete = () => {
    if (currentWorkbook) {
      setCurrentStep('extract');
    }
  };

  const handleExtractComplete = () => {
    if (currentWorkbook && currentWorkbook.status === 'ready') {
      setCurrentStep('generate');
      toast.success('Data extraction completed successfully!');
    }
  };

  const handleGenerateComplete = () => {
    if (currentWorkbook && currentWorkbook.generated_workbook_path) {
      toast.success('Workbook generated successfully!');
    }
  };

  const handleStartOver = () => {
    dispatch(clearWorkbook());
    setCurrentStep('upload');
    setReviewNotes('');
    toast.info('Starting new workbook session');
  };

  const handleDownload = async () => {
    if (currentWorkbook?.id) {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const token = localStorage.getItem('auth_token');
      const downloadUrl = `${API_BASE_URL}/api/strategy-workbook/${currentWorkbook.id}/download`;

      const response = await fetch(downloadUrl, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        credentials: 'include',
      });
      if (!response.ok) {
        toast.error('Failed to download workbook');
        throw new Error('Failed to download workbook');
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'Strategy_Workshop_Workbook.xlsx');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      toast.success('Workbook downloaded successfully!');
    }
  };

  // Determine current step based on workbook status
  const getCurrentStep = () => {
    if (!currentWorkbook) return 'upload';
    // Completed workbooks should always show the generate/download step
    if (currentWorkbook.status === 'completed') {
      return 'generate';
    }
    if (currentWorkbook.status === 'draft' && uploadedFiles.length > 0) {
      // Active upload session: files were just uploaded, follow the precheck flow
      // Only show clarify if the user explicitly reached that step via precheckWorkbook
      if (currentStep === 'clarify') {
        return 'clarify';
      }
      return 'extract';
    }
    // Returning to a draft workbook that already has files on the server (e.g. after page reload)
    // uploadedFiles Redux array is empty but server knows about the files via uploaded_media_ids
    if (
      currentWorkbook.status === 'draft' &&
      uploadedFiles.length === 0 &&
      (currentWorkbook.uploaded_media_ids?.length ?? 0) > 0
    ) {
      return 'extract';
    }
    if (currentWorkbook.status === 'ready' && currentWorkbook.extracted_data) {
      return 'generate';
    }
    // ready without extracted_data in response (large payload edge case) — still go to generate
    if (currentWorkbook.status === 'ready') {
      return 'generate';
    }
    // Extraction was in progress when the user left — bring them back to the extract step
    if (currentWorkbook.status === 'extracting') {
      return 'extract';
    }
    return currentStep;
  };

  const activeStep = getCurrentStep();

  // Map the active step to the visible stepper phase (clarify is part of the extract phase)
  const visibleStep = activeStep === 'clarify' ? 'extract' : activeStep;
  const stepOrder = ['upload', 'extract', 'generate'] as const;
  const currentStepIndex = stepOrder.indexOf(visibleStep as typeof stepOrder[number]);

  // A step is complete only when the user has moved past it
  const uploadDone = currentStepIndex > 0;
  const extractDone = currentStepIndex > 1;
  const generateDone = !!currentWorkbook?.generated_workbook_path;

  // The current step is active (loading indicator), future steps are grey
  const uploadActive = currentStepIndex === 0;
  const extractActive = currentStepIndex === 1;
  const generateActive = currentStepIndex === 2 && !generateDone;

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
          <h1 className="text-3xl font-bold tracking-tight">Strategy Workbook Generator</h1>
          <p className="text-muted-foreground mt-2">
            Upload documents, extract strategic information, and generate a prefilled Excel workbook
          </p>
        </div>
        {currentWorkbook && (
          <Button variant="outline" onClick={handleStartOver}>
            Start New Workbook
          </Button>
        )}
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
          <CardDescription>Follow these steps to generate your strategy workbook</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className={`flex items-center justify-center w-8 h-8 rounded-full ${
                uploadDone ? 'bg-green-500 text-white' :
                uploadActive ? 'bg-primary text-primary-foreground' : 'bg-muted'
              }`}>
                {uploadDone ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : uploadActive ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  '1'
                )}
              </div>
              <span className={uploadActive ? 'font-semibold' : ''}>Upload Documents</span>
            </div>
            <div className="flex-1 h-px bg-border mx-4" />
            <div className="flex items-center space-x-2">
              <div className={`flex items-center justify-center w-8 h-8 rounded-full ${
                extractDone ? 'bg-green-500 text-white' :
                extractActive ? 'bg-primary text-primary-foreground' : 'bg-muted'
              }`}>
                {extractDone ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : extractActive ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  '2'
                )}
              </div>
              <span className={extractActive ? 'font-semibold' : ''}>Extract Data</span>
            </div>
            <div className="flex-1 h-px bg-border mx-4" />
            <div className="flex items-center space-x-2">
              <div className={`flex items-center justify-center w-8 h-8 rounded-full ${
                generateDone ? 'bg-green-500 text-white' :
                generateActive ? 'bg-primary text-primary-foreground' : 'bg-muted'
              }`}>
                {generateDone ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : generateActive ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  '3'
                )}
              </div>
              <span className={generateActive ? 'font-semibold' : ''}>Generate Workbook</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Step Components */}
      {activeStep === 'upload' && (
        <UploadStep
          onComplete={handleUploadComplete}
          isLoading={isLoading}
          workbookId={currentWorkbook?.id}
        />
      )}

      {activeStep === 'clarify' && currentWorkbook && (
        <ClarifyStep
          onComplete={handleClarifyComplete}
        />
      )}

      {activeStep === 'extract' && currentWorkbook && (
        <ExtractStep
          workbookId={currentWorkbook.id}
          onComplete={handleExtractComplete}
          isExtracting={isExtracting}
        />
      )}

      {activeStep === 'generate' && currentWorkbook && (
        <GenerateStep
          workbookId={currentWorkbook.id}
          extractedData={currentWorkbook.extracted_data}
          onComplete={handleGenerateComplete}
          onDownload={handleDownload}
          isGenerating={isGenerating}
          isCompleted={currentWorkbook.status === 'completed'}
          reviewNotes={reviewNotes}
          onReviewNotesChange={setReviewNotes}
        />
      )}
    </div>
  );
}

