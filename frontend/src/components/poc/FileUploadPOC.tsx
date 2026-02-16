/**
 * POC: File Upload Component with Drag-and-Drop
 * BBA Report Builder workflow: Steps 1-7
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, X, CheckCircle2, AlertCircle, Loader2, FileText, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { ContextCaptureQuestionnaire, QuestionnaireData } from './ContextCaptureQuestionnaire';
import { DraftFindingsStep, type Finding } from './DraftFindingsStep';
import { ExpandedFindingsStep, type ExpandedFinding } from './ExpandedFindingsStep';
import { SnapshotTableStep, type SnapshotTable } from './SnapshotTableStep';
import { TwelveMonthPlanStep, type TwelveMonthPlan } from './TwelveMonthPlanStep';
import { ReviewEditStep } from './ReviewEditStep';
import { TaskPlannerStep } from './TaskPlannerStep';
import PresentationStep from './PresentationStep';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// localStorage keys for persistence
const STORAGE_KEYS = {
  PROJECT_ID: 'bba_project_id',
  CURRENT_STEP: 'bba_current_step',
  MAX_STEP: 'bba_max_step',
  QUESTIONNAIRE: 'bba_questionnaire_data',
  ENGAGEMENT_ID: 'bba_engagement_id',
} as const;

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
  engagementId?: string;
}

export function FileUploadPOC({ className, engagementId }: FileUploadPOCProps) {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9>(1);
  const [isQuestionnaireSubmitting, setIsQuestionnaireSubmitting] = useState(false);
  const [maxStepReached, setMaxStepReached] = useState<number>(1);
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

  const [stepLoadingStates, setStepLoadingStates] = useState<Record<number, boolean>>({
    3: false, 
    4: false, 
    5: false, 
    6: false, 
    7: false, 
    8: false, 
  });
  const [isRestoring, setIsRestoring] = useState(true);

  // Update loading state for a specific step
  const updateStepLoadingState = useCallback((step: number, isLoading: boolean) => {
    setStepLoadingStates((prev) => ({
      ...prev,
      [step]: isLoading,
    }));
  }, []);

  // Restore state from backend based on engagement ID
  useEffect(() => {
    const restoreState = async () => {
      try {
        if (!engagementId) {
          setIsRestoring(false);
          return;
        }

        // First, try to find existing BBA project for this engagement from backend
        try {
          const token = localStorage.getItem('auth_token');
          const response = await fetch(`${API_BASE_URL}/api/poc?engagement_id=${engagementId}`, {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            credentials: 'include',
          });

          if (response.ok) {
            const result = await response.json();
            const project = result.project;

            if (project && project.id) {
              // Found existing project for this engagement - restore everything from backend
              setProjectId(project.id);
              localStorage.setItem(STORAGE_KEYS.PROJECT_ID, project.id);
              localStorage.setItem(STORAGE_KEYS.ENGAGEMENT_ID, engagementId);

              // Restore files from file_mappings
              if (project.file_mappings && typeof project.file_mappings === 'object') {
                const restoredFiles: UploadedFile[] = Object.entries(project.file_mappings).map(
                  ([filename, fileId]) => {
                    const dummyFile = new File([], filename, {
                      type: 'application/octet-stream',
                    });
                    
                    return {
                      id: `${Date.now()}-${Math.random()}`,
                      file: dummyFile,
                      status: 'success' as const,
                      progress: 100,
                      fileId: fileId as string,
                    };
                  }
                );
                setFiles(restoredFiles);
              }

              // Restore questionnaire data from backend if available
              if (project.client_name || project.industry || project.company_size) {
                setQuestionnaireData({
                  clientName: project.client_name || '',
                  industry: project.industry || '',
                  companySize: project.company_size || '',
                  locations: project.locations || '',
                  exclusions: project.exclusions || '',
                  constraints: project.constraints || '',
                  preferredRanking: project.preferred_ranking || '',
                  strategicPriorities: project.strategic_priorities || '',
                  excludeSaleReadiness: project.exclude_sale_readiness || false,
                });
              }

              // Restore step progress from backend (this is the key fix!)
              if (project.current_step !== null && project.current_step !== undefined) {
                const stepNum = parseInt(String(project.current_step), 10) as 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
                if (stepNum >= 1 && stepNum <= 9) {
                  setCurrentStep(stepNum);
                  localStorage.setItem(STORAGE_KEYS.CURRENT_STEP, stepNum.toString());
                }
              } else {
                // Default to step 1 if no step is set
                setCurrentStep(1);
                localStorage.setItem(STORAGE_KEYS.CURRENT_STEP, '1');
              }
              
              if (project.max_step_reached !== null && project.max_step_reached !== undefined) {
                const maxStepNum = parseInt(String(project.max_step_reached), 10);
                if (maxStepNum >= 1 && maxStepNum <= 9) {
                  setMaxStepReached(maxStepNum);
                  localStorage.setItem(STORAGE_KEYS.MAX_STEP, maxStepNum.toString());
                }
              } else if (project.status) {
                // Fallback to status-based inference if max_step_reached is not set
                const statusToStep: Record<string, number> = {
                  'uploaded': 1,
                  'questionnaire_completed': 2,
                  'draft_findings': 3,
                  'expanded_findings': 4,
                  'snapshot_table': 5,
                  'twelve_month_plan': 6,
                  'completed': 7,
                };
                const stepFromStatus = statusToStep[project.status] || 1;
                setMaxStepReached(stepFromStatus);
                localStorage.setItem(STORAGE_KEYS.MAX_STEP, stepFromStatus.toString());
              } else {
                setMaxStepReached(1);
                localStorage.setItem(STORAGE_KEYS.MAX_STEP, '1');
              }

              setIsRestoring(false);
              return; // Successfully restored from backend
            }
          }
        } catch (error) {
          console.error('Error fetching BBA project for engagement:', error);
        }

        // No existing project found - check localStorage for backward compatibility
        const storedProjectId = localStorage.getItem(STORAGE_KEYS.PROJECT_ID);
        const storedEngagementId = localStorage.getItem(STORAGE_KEYS.ENGAGEMENT_ID);
        
        if (storedProjectId && storedEngagementId === engagementId) {
          // Use stored project if it matches current engagement
          setProjectId(storedProjectId);
          
          // Restore step from localStorage as fallback
          const storedStep = localStorage.getItem(STORAGE_KEYS.CURRENT_STEP);
          const storedMaxStep = localStorage.getItem(STORAGE_KEYS.MAX_STEP);
          if (storedStep) {
            const stepNum = parseInt(storedStep, 10) as 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
            if (stepNum >= 1 && stepNum <= 9) {
              setCurrentStep(stepNum);
            }
          }
          if (storedMaxStep) {
            const maxStepNum = parseInt(storedMaxStep, 10);
            if (maxStepNum >= 1 && maxStepNum <= 9) {
              setMaxStepReached(maxStepNum);
            }
          }

          // Try to fetch project details from backend
          try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE_URL}/api/poc/${storedProjectId}`, {
              method: 'GET',
              headers: {
                'Content-Type': 'application/json',
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
              },
              credentials: 'include',
            });

            if (response.ok) {
              const result = await response.json();
              const project = result.project;

              // Restore files
              if (project.file_mappings && typeof project.file_mappings === 'object') {
                const restoredFiles: UploadedFile[] = Object.entries(project.file_mappings).map(
                  ([filename, fileId]) => {
                    const dummyFile = new File([], filename, {
                      type: 'application/octet-stream',
                    });
                    
                    return {
                      id: `${Date.now()}-${Math.random()}`,
                      file: dummyFile,
                      status: 'success' as const,
                      progress: 100,
                      fileId: fileId as string,
                    };
                  }
                );
                setFiles(restoredFiles);
              }

              // Restore questionnaire data
              if (project.client_name || project.industry || project.company_size) {
                setQuestionnaireData({
                  clientName: project.client_name || '',
                  industry: project.industry || '',
                  companySize: project.company_size || '',
                  locations: project.locations || '',
                  exclusions: project.exclusions || '',
                  constraints: project.constraints || '',
                  preferredRanking: project.preferred_ranking || '',
                  strategicPriorities: project.strategic_priorities || '',
                  excludeSaleReadiness: project.exclude_sale_readiness || false,
                });
              }

              // Restore step progress from backend (overrides localStorage)
              if (project.current_step !== null && project.current_step !== undefined) {
                const stepNum = parseInt(String(project.current_step), 10) as 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
                if (stepNum >= 1 && stepNum <= 9) {
                  setCurrentStep(stepNum);
                  localStorage.setItem(STORAGE_KEYS.CURRENT_STEP, stepNum.toString());
                }
              }
              
              if (project.max_step_reached !== null && project.max_step_reached !== undefined) {
                const maxStepNum = parseInt(String(project.max_step_reached), 10);
                if (maxStepNum >= 1 && maxStepNum <= 9) {
                  setMaxStepReached(maxStepNum);
                  localStorage.setItem(STORAGE_KEYS.MAX_STEP, maxStepNum.toString());
                }
              }
            }
          } catch (error) {
            console.error('Error restoring project data:', error);
          }
        } else {
          // No project found - clear any stale localStorage data for different engagement
          if (storedEngagementId && storedEngagementId !== engagementId) {
            localStorage.removeItem(STORAGE_KEYS.PROJECT_ID);
            localStorage.removeItem(STORAGE_KEYS.CURRENT_STEP);
            localStorage.removeItem(STORAGE_KEYS.MAX_STEP);
            localStorage.removeItem(STORAGE_KEYS.QUESTIONNAIRE);
          }
          // Store current engagement ID
          localStorage.setItem(STORAGE_KEYS.ENGAGEMENT_ID, engagementId);
          // Reset to step 1 for new engagement
          setCurrentStep(1);
          setMaxStepReached(1);
        }
      } catch (error) {
        console.error('Error restoring state:', error);
      } finally {
        setIsRestoring(false);
      }
    };

    restoreState();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engagementId]); // Only run on mount or when engagementId changes

  // Persist project ID to localStorage
  useEffect(() => {
    if (projectId) {
      localStorage.setItem(STORAGE_KEYS.PROJECT_ID, projectId);
      if (engagementId) {
        localStorage.setItem(STORAGE_KEYS.ENGAGEMENT_ID, engagementId);
      }
    }
  }, [projectId, engagementId]);

  // Save step progress to backend when it changes
  useEffect(() => {
    if (!isRestoring && projectId) {
      // Save to localStorage for immediate UI updates
      localStorage.setItem(STORAGE_KEYS.CURRENT_STEP, currentStep.toString());
      
      // Save to backend for persistence across engagements
      const saveStepProgress = async () => {
        try {
          const token = localStorage.getItem('auth_token');
          const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step-progress`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            credentials: 'include',
            body: JSON.stringify({
              current_step: currentStep,
            }),
          });

          if (!response.ok) {
            console.error('Failed to save step progress to backend');
          }
        } catch (error) {
          console.error('Error saving step progress:', error);
        }
      };

      saveStepProgress();
    }
  }, [currentStep, projectId, isRestoring]);

  // Save max step reached to backend when it changes
  useEffect(() => {
    if (!isRestoring && projectId) {
      // Save to localStorage for immediate UI updates
      localStorage.setItem(STORAGE_KEYS.MAX_STEP, maxStepReached.toString());
      
      // Save to backend for persistence across engagements
      const saveMaxStep = async () => {
        try {
          const token = localStorage.getItem('auth_token');
          const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step-progress`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            credentials: 'include',
            body: JSON.stringify({
              max_step_reached: maxStepReached,
            }),
          });

          if (!response.ok) {
            console.error('Failed to save max step to backend');
          }
        } catch (error) {
          console.error('Error saving max step:', error);
        }
      };

      saveMaxStep();
    }
  }, [maxStepReached, projectId, isRestoring]);

  // Persist questionnaire data to localStorage
  useEffect(() => {
    if (!isRestoring) {
      localStorage.setItem(STORAGE_KEYS.QUESTIONNAIRE, JSON.stringify(questionnaireData));
    }
  }, [questionnaireData, isRestoring]);

  const goToStep = (step: number) => {
    // Check if any step is currently loading/processing
    const isAnyStepBusy = 
      isUploading || 
      isCreatingProject || 
      isQuestionnaireSubmitting ||
      Object.values(stepLoadingStates).some(isLoading => isLoading);
    
    // Check if the current step is busy
    const isCurrentStepBusy = stepLoadingStates[currentStep] || false;
    
    // Block navigation if current step is busy (both forward and backward)
    if (isCurrentStepBusy) {
      console.log('Cannot navigate: current step is currently processing');
      return;
    }
    
    // Block forward navigation if any step is busy
    const isMovingForward = step > currentStep;
    if (isAnyStepBusy && isMovingForward) {
      console.log('Cannot navigate forward: a step is currently processing');
      return;
    }
    
    const newStep = step as 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
    const newMaxStep = Math.max(maxStepReached, step);
    
    setCurrentStep(newStep);
    setMaxStepReached(newMaxStep);
    
    // Step progress will be saved to backend via useEffect hooks
  };

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
      const url = new URL(`${API_BASE_URL}/api/poc/create-project`);
      if (engagementId) {
        url.searchParams.append('engagement_id', engagementId);
      }
      
      const response = await fetch(url.toString(), {
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
      const newProjectId = result.project_id;
      setProjectId(newProjectId);
      // Store in localStorage
      localStorage.setItem(STORAGE_KEYS.PROJECT_ID, newProjectId);
      if (engagementId) {
        localStorage.setItem(STORAGE_KEYS.ENGAGEMENT_ID, engagementId);
      }
      return newProjectId;
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

    setIsQuestionnaireSubmitting(true);
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
      goToStep(3);
    } catch (error) {
      console.error('Failed to submit questionnaire:', error);
    } finally {
      setIsQuestionnaireSubmitting(false);
    }
  };

  const pendingCount = files.filter((f) => f.status === 'pending').length;
  const successCount = files.filter((f) => f.status === 'success').length;
  const errorCount = files.filter((f) => f.status === 'error').length;

  // Phase 1 steps (1-7): Word Report Generation
  // Phase 2 steps (8+):  Excel Engagement Planner
  const phase1Steps = [
    { step: 1, label: 'Upload Files' },
    { step: 2, label: 'Context Capture' },
    { step: 3, label: 'Draft Findings' },
    { step: 4, label: 'Expand Findings' },
    { step: 5, label: 'Snapshot Table' },
    { step: 6, label: '12-Month Plan' },
    { step: 7, label: 'Review & Export' },
  ] as const;

  const phase2Steps = [
    { step: 8, label: 'Task Planner' },
  ] as const;

  const phase3Steps = [
    { step: 9, label: 'Presentation' },
  ] as const;

  const isPhase3 = currentStep >= 9;
  const isPhase2 = currentStep === 8;
  const currentPhase = isPhase3 ? 3 : isPhase2 ? 2 : 1;
  const displayStep = isPhase3 ? currentStep - 8 : isPhase2 ? currentStep - 7 : currentStep;
  const stepLabels: Record<number, string> = {
    1: 'Upload Files',
    2: 'Context Capture',
    3: 'Draft Findings',
    4: 'Expand Findings',
    5: 'Snapshot Table',
    6: '12-Month Plan',
    7: 'Review & Export',
    8: 'Task Planner',
    9: 'Presentation',
  };
  
  const isAnyStepBusy =
    isUploading || 
    isCreatingProject || 
    isQuestionnaireSubmitting ||
    Object.values(stepLoadingStates).some(isLoading => isLoading);

  // Show loading state while restoring
  if (isRestoring) {
    return (
      <Card className={cn('w-full max-w-8xl mx-auto', className)}>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground">Loading your project...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn('w-full max-w-8xl mx-auto', className)}>
      <CardHeader>
        <CardTitle>BBA Report Builder</CardTitle>

      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3 mb-6">
          {/* Phase 1 */}
          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground mb-1">
              Phase 1
            </p>
            <div className="flex flex-wrap justify-start items-center gap-1">
              {[1, 2, 3, 4, 5, 6, 7].map((step) => {
                // Check if current step is busy
                const isCurrentStepBusy = stepLoadingStates[currentStep] || false;
                // Block navigation if current step is busy
                const isMovingForward = step > currentStep;
                const isEnabled = step <= maxStepReached && !isCurrentStepBusy && (!isAnyStepBusy || !isMovingForward);

                return (
                  <React.Fragment key={step}>
                    {step > 1 && (
                      <ArrowRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                    )}

                    <button
                      type="button"
                      onClick={() => {
                        if (isEnabled) {
                          goToStep(step);
                        }
                      }}
                      disabled={!isEnabled}
                      className={cn(
                        'flex items-center gap-1 px-4 py-2 rounded text-xs font-medium',
                        currentStep === step
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground',
                        isEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'
                      )}
                    >
                      <span>
                        {step}. {stepLabels[step]}
                      </span>
                      {currentStep > step && <CheckCircle2 className="w-3 h-3" />}
                    </button>
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Phase 2 */}
          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground mb-1">
              Phase 2
            </p>
            <div className="flex flex-wrap justify-start items-center gap-1">
              {[8].map((step) => {
                // Check if current step is busy
                const isCurrentStepBusy = stepLoadingStates[currentStep] || false;
                // Block navigation if current step is busy
                const isMovingForward = step > currentStep;
                // Phase 2 is reachable once user has reached step 7 (Review & Export) or beyond
                const canReachPhase2 = maxStepReached >= 7;
                const isEnabled = (step <= maxStepReached || (step === 8 && canReachPhase2)) && !isCurrentStepBusy && (!isAnyStepBusy || !isMovingForward);

                return (
                  <button
                    key={step}
                    type="button"
                    onClick={() => {
                      if (isEnabled) {
                        goToStep(step);
                      }
                    }}
                    disabled={!isEnabled}
                    className={cn(
                      'flex items-center gap-1 px-4 py-2 rounded text-xs font-medium',
                      currentStep === step
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground',
                      isEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'
                    )}
                  >
                    {/* Shown as Phase 2 – Step 1 */}
                    <span>1. {stepLabels[step]}</span>
                    {currentStep > step && <CheckCircle2 className="w-3 h-3" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Phase 3 */}
          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground mb-1">
              Phase 3
            </p>
            <div className="flex flex-wrap justify-start items-center gap-1">
              {phase3Steps.map(({ step, label }, idx) => {
                // Check if current step is busy
                const isCurrentStepBusy = stepLoadingStates[currentStep] || false;
                // Block navigation if current step is busy
                const isMovingForward = step > currentStep;
                const isEnabled = step <= maxStepReached && !isCurrentStepBusy && (!isAnyStepBusy || !isMovingForward);

                return (
                  <React.Fragment key={step}>
                    {idx > 0 && (
                      <ArrowRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        if (isEnabled) {
                          goToStep(step);
                        }
                      }}
                      disabled={!isEnabled}
                      className={cn(
                        'flex items-center gap-1 px-4 py-2 rounded text-xs font-medium',
                        currentStep === step
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground',
                        isEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'
                      )}
                    >
                      <span>{step - 8}. {label}</span>
                      {currentStep > step && <CheckCircle2 className="w-3 h-3" />}
                    </button>
                  </React.Fragment>
                );
              })}
            </div>
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
                    <span>Total files uploaded: {files.length}</span>
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

            {/* Continue to Step 2 Button */}
            {successCount > 0 && (
              <div className="flex justify-end pt-4 border-t">
                <Button
                  onClick={() => goToStep(2)}
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
            onBack={() => goToStep(1)}
            files={files}
            successCount={successCount}
            isSubmitting={isQuestionnaireSubmitting}
          />
        )}

        {/* Step 3: Draft Findings */}
        {currentStep === 3 && projectId && (
          <DraftFindingsStep
            projectId={projectId}
            onComplete={() => goToStep(4)}
            onBack={() => goToStep(2)}
            onLoadingStateChange={(isLoading) => updateStepLoadingState(3, isLoading)}
          />
        )}

        {/* Step 4: Expand Findings */}
        {currentStep === 4 && projectId && (
          <ExpandedFindingsStep
            projectId={projectId}
            onComplete={() => goToStep(5)}
            onBack={() => goToStep(3)}
            onLoadingStateChange={(isLoading) => updateStepLoadingState(4, isLoading)}
          />
        )}

        {/* Step 5: Snapshot Table */}
        {currentStep === 5 && projectId && (
          <SnapshotTableStep
            projectId={projectId}
            onComplete={() => goToStep(6)}
            onBack={() => goToStep(4)}
            onLoadingStateChange={(isLoading) => updateStepLoadingState(5, isLoading)}
          />
        )}

        {/* Step 6: 12-Month Plan */}
        {currentStep === 6 && projectId && (
          <TwelveMonthPlanStep
            projectId={projectId}
            onComplete={() => goToStep(7)}
            onBack={() => goToStep(5)}
            onLoadingStateChange={(isLoading) => updateStepLoadingState(6, isLoading)}
          />
        )}

        {/* Step 7: Review & Export */}
        {currentStep === 7 && projectId && (
          <ReviewEditStep
            projectId={projectId}
            onBack={() => goToStep(6)}
            onContinueToPhase2={() => goToStep(8)}
            onLoadingStateChange={(isLoading) => updateStepLoadingState(7, isLoading)}
          />
        )}

        {/* Step 8: Phase 2 – Task Planner (Excel Generator) */}
        {currentStep === 8 && projectId && (
          <TaskPlannerStep
            projectId={projectId}
            onBack={() => setCurrentStep(7)}
            onContinueToPhase3={() => setCurrentStep(9)}
          />
        )}

        {/* Step 9: Phase 3 – Presentation Generator */}
        {currentStep === 9 && projectId && (
          <PresentationStep
            projectId={projectId}
            onBack={() => setCurrentStep(8)}
          />
        )}
      </CardContent>
    </Card>
  );
}
