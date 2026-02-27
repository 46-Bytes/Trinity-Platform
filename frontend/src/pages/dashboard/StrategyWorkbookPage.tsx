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
  const initialLoadDone = useRef(false);

  // Load workbook from navigation state (when coming from FollowUpToolsTab)
  useEffect(() => {
    if (initialLoadDone.current) return;
    const stateWorkbookId = (location.state as { workbookId?: string } | null)?.workbookId;
    if (stateWorkbookId && (!currentWorkbook || currentWorkbook.id !== stateWorkbookId)) {
      initialLoadDone.current = true;
      dispatch(getWorkbook(stateWorkbookId));
    }
  }, [location.state, currentWorkbook, dispatch]);

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

  const handleDownload = () => {
    if (currentWorkbook?.id) {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const token = localStorage.getItem('auth_token');
      const downloadUrl = `${API_BASE_URL}/api/strategy-workbook/${currentWorkbook.id}/download`;
      
      // Use fetch with token to download the file
      fetch(downloadUrl, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error('Failed to download workbook');
          }
          return response.blob();
        })
        .then((blob) => {
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.setAttribute('download', 'Strategy_Workshop_Workbook.xlsx');
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          window.URL.revokeObjectURL(url);
          toast.success('Workbook downloaded successfully!');
        })
        .catch((error) => {
          console.error('Download failed:', error);
          toast.error('Failed to download workbook');
        });
    }
  };

  // Determine current step based on workbook status
  const getCurrentStep = () => {
    if (!currentWorkbook) return 'upload';
    if (currentWorkbook.status === 'draft' && uploadedFiles.length > 0) {
      // While still in draft, show clarify step first, then extract
      if (currentStep === 'clarify' || currentStep === 'upload') {
        return 'clarify';
      }
      return 'extract';
    }
    if (
      (currentWorkbook.status === 'ready' || currentWorkbook.status === 'completed') &&
      currentWorkbook.extracted_data
    ) {
      return 'generate';
    }
    return currentStep;
  };

  const activeStep = getCurrentStep();

  // Derive completion state from actual workbook data, not the current step
  const uploadDone = !!currentWorkbook;
  const extractDone = !!currentWorkbook?.extracted_data;
  const generateDone = !!currentWorkbook?.generated_workbook_path;

  // Determine which step is actively in-progress (not yet completed)
  const visibleStep = activeStep === 'clarify' ? 'extract' : activeStep;
  const uploadActive = visibleStep === 'upload' && !uploadDone;
  const extractActive = (visibleStep === 'extract' || visibleStep === 'upload') && uploadDone && !extractDone;
  const generateActive = visibleStep === 'generate' && extractDone && !generateDone;

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
          reviewNotes={reviewNotes}
          onReviewNotesChange={setReviewNotes}
        />
      )}
    </div>
  );
}

