import { useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { 
  uploadDocuments, 
  extractData, 
  generateWorkbook, 
  clearWorkbook,
  setReviewNotes,
  precheckWorkbook,
} from '@/store/slices/strategyWorkbookReducer';
import { UploadStep } from '@/components/strategy-workbook/UploadStep';
import { ClarifyStep } from '@/components/strategy-workbook/ClarifyStep';
import { ExtractStep } from '@/components/strategy-workbook/ExtractStep';
import { GenerateStep } from '@/components/strategy-workbook/GenerateStep';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export default function StrategyWorkbookPage() {
  const dispatch = useAppDispatch();
  const { currentWorkbook, isLoading, isExtracting, isGenerating, error, uploadedFiles } = useAppSelector(
    (state) => state.strategyWorkbook
  );

  const [currentStep, setCurrentStep] = useState<'upload' | 'clarify' | 'extract' | 'generate'>('upload');
  const [reviewNotes, setReviewNotes] = useState('');

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
  const progressStep = activeStep === 'clarify' ? 'extract' : activeStep;

  return (
    <div className="container mx-auto p-6 space-y-6">
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
                progressStep === 'upload' ? 'bg-primary text-primary-foreground' :
                currentWorkbook ? 'bg-green-500 text-white' : 'bg-muted'
              }`}>
                {currentWorkbook && progressStep !== 'upload' ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : progressStep === 'upload' ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  '1'
                )}
              </div>
              <span className={progressStep === 'upload' ? 'font-semibold' : ''}>Upload Documents</span>
            </div>
            <div className="flex-1 h-px bg-border mx-4" />
            <div className="flex items-center space-x-2">
              <div className={`flex items-center justify-center w-8 h-8 rounded-full ${
                progressStep === 'extract' ? 'bg-primary text-primary-foreground' :
                currentWorkbook?.status === 'ready' ? 'bg-green-500 text-white' : 'bg-muted'
              }`}>
                {currentWorkbook?.status === 'ready' && progressStep !== 'extract' ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : progressStep === 'extract' ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  '2'
                )}
              </div>
              <span className={progressStep === 'extract' ? 'font-semibold' : ''}>Extract Data</span>
            </div>
            <div className="flex-1 h-px bg-border mx-4" />
            <div className="flex items-center space-x-2">
              <div className={`flex items-center justify-center w-8 h-8 rounded-full ${
                progressStep === 'generate' ? 'bg-primary text-primary-foreground' :
                currentWorkbook?.generated_workbook_path ? 'bg-green-500 text-white' : 'bg-muted'
              }`}>
                {currentWorkbook?.generated_workbook_path && progressStep !== 'generate' ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : progressStep === 'generate' ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  '3'
                )}
              </div>
              <span className={progressStep === 'generate' ? 'font-semibold' : ''}>Generate Workbook</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Step Components */}
      {activeStep === 'upload' && (
        <UploadStep 
          onComplete={handleUploadComplete}
          isLoading={isLoading}
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

