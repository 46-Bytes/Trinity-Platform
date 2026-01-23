/**
 * POC: File Upload Component with Drag-and-Drop
 * This is a standalone POC component, separate from the main file upload system.
 */
import React, { useState, useCallback, useRef } from 'react';
import { Upload, X, CheckCircle2, AlertCircle, Loader2, FileText, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { ContextCaptureQuestionnaire, QuestionnaireData } from './ContextCaptureQuestionnaire';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// File validation constants
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB
const ALLOWED_FILE_TYPES = [
  'application/pdf',
  'text/plain',
  'text/csv',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/jpeg',
  'image/png',
  'image/gif',
  'application/json',
  'text/markdown',
];

interface UploadedFile {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  progress: number;
  fileId?: string; // OpenAI file_id
  error?: string;
  openaiInfo?: {
    bytes?: number;
    purpose?: string;
    created_at?: number;
  };
}

interface FileUploadPOCProps {
  className?: string;
}

export function FileUploadPOC({ className }: FileUploadPOCProps) {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [currentStep, setCurrentStep] = useState<1 | 2>(1);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [questionnaireData, setQuestionnaireData] = useState<QuestionnaireData>({
    clientName: '',
    industry: '',
    companySize: '',
    locations: '',
    exclusions: '',
    constraints: '',
    preferredRanking: '',
    strategicPriorities: '',
    excludeSaleReadiness: false,
  });
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Validate file
  const validateFile = (file: File): { valid: boolean; error?: string } => {
    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return {
        valid: false,
        error: `File size exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`,
      };
    }

    // Check file type
    if (!ALLOWED_FILE_TYPES.includes(file.type)) {
      return {
        valid: false,
        error: `File type "${file.type}" is not allowed`,
      };
    }

    return { valid: true };
  };

  // Add files to the list
  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const fileArray = Array.from(newFiles);
    const validFiles: UploadedFile[] = [];

    fileArray.forEach((file) => {
      const validation = validateFile(file);
      if (validation.valid) {
        validFiles.push({
          id: `${Date.now()}-${Math.random()}`,
          file,
          status: 'pending',
          progress: 0,
        });
      } else {
        // Show error for invalid files
        console.error(`File ${file.name} is invalid: ${validation.error}`);
        // You could add a toast notification here
      }
    });

    setFiles((prev) => [...prev, ...validFiles]);
  }, []);

  // Handle file input change
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
    }
  };

  // Handle drag and drop
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  };

  // Create BBA project if not exists
  const ensureProject = async (): Promise<string> => {
    if (projectId) {
      return projectId;
    }

    setIsCreatingProject(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/create-project`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to create project' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to create project`);
      }

      const result = await response.json();
      setProjectId(result.project_id);
      return result.project_id;
    } catch (error) {
      console.error('Failed to create project:', error);
      throw error;
    } finally {
      setIsCreatingProject(false);
    }
  };

  // Upload files to backend
  const handleUpload = async () => {
    const pendingFiles = files.filter((f) => f.status === 'pending');
    if (pendingFiles.length === 0) {
      return;
    }

    setIsUploading(true);

    try {
      // Ensure project exists
      const currentProjectId = await ensureProject();

      // Create FormData
      const formData = new FormData();
      pendingFiles.forEach((fileObj) => {
        formData.append('files', fileObj.file);
      });

      // Update status to uploading
      setFiles((prev) =>
        prev.map((f) =>
          f.status === 'pending' ? { ...f, status: 'uploading', progress: 0 } : f
        )
      );

      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/${currentProjectId}/upload`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();

      // Update files with results
      setFiles((prev) => {
        const updated = [...prev];
        result.files.forEach((uploadResult: any) => {
          const fileIndex = updated.findIndex(
            (f) => f.file.name === uploadResult.filename
          );
          if (fileIndex !== -1) {
            updated[fileIndex] = {
              ...updated[fileIndex],
              status: uploadResult.status === 'success' ? 'success' : 'error',
              progress: 100,
              fileId: uploadResult.file_id || undefined,
              error: uploadResult.error || undefined,
              openaiInfo: uploadResult.openai_info || undefined,
            };
          }
        });
        return updated;
      });
    } catch (error) {
      console.error('Upload error:', error);
      // Update all uploading files to error
      setFiles((prev) =>
        prev.map((f) =>
          f.status === 'uploading'
            ? {
                ...f,
                status: 'error',
                error: error instanceof Error ? error.message : 'Upload failed',
              }
            : f
        )
      );
    } finally {
      setIsUploading(false);
    }
  };

  // Remove file from list
  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  // Clear all files
  const clearAll = () => {
    setFiles([]);
  };

  // Handle questionnaire form changes
  const handleQuestionnaireChange = (field: keyof QuestionnaireData, value: string | boolean) => {
    setQuestionnaireData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  // Handle questionnaire submission
  const handleQuestionnaireSubmit = async () => {
    if (!projectId) {
      console.error('No project ID available');
      return;
    }

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/submit-questionnaire`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify(questionnaireData),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to submit questionnaire' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to submit questionnaire`);
      }

      const result = await response.json();
      console.log('Questionnaire submitted successfully:', result);
      // TODO: Navigate to next step or show success message
    } catch (error) {
      console.error('Failed to submit questionnaire:', error);
      // TODO: Show error toast/notification
    }
  };

  const pendingCount = files.filter((f) => f.status === 'pending').length;
  const successCount = files.filter((f) => f.status === 'success').length;
  const errorCount = files.filter((f) => f.status === 'error').length;

  return (
    <Card className={cn('w-full max-w-4xl mx-auto', className)}>
      <CardHeader>
        <CardTitle>File Upload POC</CardTitle>
        <CardDescription>
          {currentStep === 1 
            ? 'Step 1: Upload multiple files to OpenAI Files API. Files are validated on the frontend.'
            : 'Step 2: Context Capture - Provide client information and preferences.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Step Indicator */}
        <div className="flex items-center gap-2 mb-6">
          <div className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg",
            currentStep === 1 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
          )}>
            <span className="font-medium">Step 1: Upload Files</span>
            {successCount > 0 && currentStep === 2 && (
              <CheckCircle2 className="w-4 h-4" />
            )}
          </div>
          <ArrowRight className="w-4 h-4 text-muted-foreground" />
          <div className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg",
            currentStep === 2 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
          )}>
            <span className="font-medium">Step 2: Context Capture</span>
          </div>
        </div>

        {/* Step 1: File Upload */}
        {currentStep === 1 && (
          <>
        {/* Drag and Drop Zone */}
        <div
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={cn(
            'border-2 border-dashed rounded-lg p-12 text-center transition-colors',
            isDragging
              ? 'border-primary bg-primary/5'
              : 'border-muted-foreground/25 hover:border-muted-foreground/50'
          )}
        >
          <Upload className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
          <p className="text-lg font-medium mb-2">
            Drag and drop files here, or click to select
          </p>
          <p className="text-sm text-muted-foreground mb-4">
            Max file size: {MAX_FILE_SIZE / (1024 * 1024)}MB
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            Select Files
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileInputChange}
            accept={ALLOWED_FILE_TYPES.join(',')}
          />
        </div>

        {/* File List */}
        {files.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>Total: {files.length}</span>
                {pendingCount > 0 && <span>Pending: {pendingCount}</span>}
                {successCount > 0 && (
                  <span className="text-green-600">Success: {successCount}</span>
                )}
                {errorCount > 0 && (
                  <span className="text-red-600">Error: {errorCount}</span>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={clearAll}
                  disabled={isUploading}
                >
                  Clear All
                </Button>
                <Button
                  type="button"
                  onClick={handleUpload}
                  disabled={isUploading || pendingCount === 0}
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="mr-2 h-4 w-4" />
                      Upload {pendingCount > 0 && `(${pendingCount})`}
                    </>
                  )}
                </Button>
              </div>
            </div>

            <div className="space-y-2 max-h-96 overflow-y-auto">
              {files.map((fileObj) => (
                <div
                  key={fileObj.id}
                  className="flex items-center gap-4 p-3 border rounded-lg bg-card"
                >
                  <FileText className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{fileObj.file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(fileObj.file.size / 1024).toFixed(2)} KB
                    </p>
                    {fileObj.status === 'uploading' && (
                      <Progress value={fileObj.progress} className="mt-2 h-1" />
                    )}
                    {fileObj.status === 'success' && fileObj.fileId && (
                      <p className="text-xs text-green-600 mt-1">
                        OpenAI File ID: {fileObj.fileId}
                      </p>
                    )}
                    {fileObj.status === 'error' && fileObj.error && (
                      <p className="text-xs text-red-600 mt-1">{fileObj.error}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {fileObj.status === 'success' && (
                      <CheckCircle2 className="h-5 w-5 text-green-600" />
                    )}
                    {fileObj.status === 'error' && (
                      <AlertCircle className="h-5 w-5 text-red-600" />
                    )}
                    {fileObj.status === 'uploading' && (
                      <Loader2 className="h-5 w-5 text-primary animate-spin" />
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => removeFile(fileObj.id)}
                      disabled={fileObj.status === 'uploading'}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

            {/* File Mappings Display */}
            {successCount > 0 && (
              <div className="mt-4 p-4 bg-muted rounded-lg">
                <p className="text-sm font-medium mb-2">File Mappings (stored in session):</p>
                <div className="space-y-1">
                  {files
                    .filter((f) => f.status === 'success' && f.fileId)
                    .map((f) => (
                      <div key={f.id} className="text-xs font-mono">
                        <span className="text-muted-foreground">{f.file.name}</span>
                        <span className="mx-2">→</span>
                        <span className="text-primary">{f.fileId}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Continue to Step 2 Button */}
            {successCount > 0 && (
              <div className="flex justify-end pt-4 border-t">
                <Button
                  onClick={() => setCurrentStep(2)}
                  disabled={successCount === 0}
                >
                  Continue to Step 2
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            )}
          </>
        )}

        {/* Step 2: Questionnaire */}
        {currentStep === 2 && (
          <ContextCaptureQuestionnaire
            questionnaireData={questionnaireData}
            onQuestionnaireChange={handleQuestionnaireChange}
            onSubmit={handleQuestionnaireSubmit}
            onBack={() => setCurrentStep(1)}
            files={files}
            successCount={successCount}
          />
        )}
      </CardContent>
    </Card>
  );
}
