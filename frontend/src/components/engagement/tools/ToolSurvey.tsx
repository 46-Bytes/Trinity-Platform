import { useState, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { ToolQuestion } from './ToolQuestion';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  fetchDiagnosticByEngagement,
  updateDiagnosticResponses,
  updateLocalResponses,
  submitDiagnostic,
} from '@/store/slices/diagnosticReducer';
import { updateEngagement } from '@/store/slices/engagementReducer';
import { useAuth } from '@/context/AuthContext';
import surveyData from '@/questions/diagnostic-survey.json';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface ToolSurveyProps {
  engagementId: string;
  toolType?: 'diagnostic'; // Can extend for other tools
}

export function ToolSurvey({ engagementId, toolType = 'diagnostic' }: ToolSurveyProps) {
  const dispatch = useAppDispatch();
  const { user } = useAuth();
  const { diagnostic, isSaving, isLoading, isSubmitting, error } = useAppSelector((state) => state.diagnostic);
  
  const [currentPage, setCurrentPage] = useState(0);
  const [localResponses, setLocalResponses] = useState<Record<string, any>>({});
  const [completedPages, setCompletedPages] = useState<number[]>([]);
  const [engagementStatusUpdated, setEngagementStatusUpdated] = useState(false);
  
  const pages = surveyData.pages;
  const totalPages = pages.length;
  const currentPageData = pages[currentPage];
  const progress = ((currentPage + 1) / totalPages) * 100;

  // Fetch diagnostic when component mounts
  useEffect(() => {
    if (engagementId && toolType === 'diagnostic') {
      dispatch(fetchDiagnosticByEngagement(engagementId));
    }
  }, [dispatch, engagementId, toolType]);

  // Merge Redux responses (source of truth) with local unsaved changes
  const responses = useMemo(() => {
    const savedResponses = diagnostic?.userResponses || {};
    return {
      ...savedResponses,
      ...localResponses, // Local changes override saved responses
    };
  }, [diagnostic?.userResponses, localResponses]);

  const handleSaveProgress = async () => {
    if (!diagnostic?.id) {
      toast.error('Diagnostic not loaded yet');
      return;
    }

    try {
      // Get responses for current page only (chunk-wise update)
      const currentPageResponses: Record<string, any> = {};
      currentPageData.elements.forEach((element) => {
        if (responses[element.name] !== undefined) {
          currentPageResponses[element.name] = responses[element.name];
        }
      });

      // Update local state immediately for better UX
      dispatch(updateLocalResponses(currentPageResponses));

      // PATCH to backend with chunk of responses
      // Backend will merge these with existing responses
      const updatedDiagnostic = await dispatch(updateDiagnosticResponses({
        diagnosticId: diagnostic.id,
        updates: {
          userResponses: currentPageResponses,
          status: 'in_progress',
        },
      })).unwrap();
      
      // Clear only the current page's responses from localResponses
      // The backend has merged and saved them, so they're now in Redux state
      // Keep responses from other pages that might not be saved yet
      setLocalResponses((prev) => {
        const updated = { ...prev };
        currentPageData.elements.forEach((element) => {
          // Only clear if the response is now in the backend (saved)
          if (updatedDiagnostic?.userResponses?.[element.name] !== undefined) {
            delete updated[element.name];
          }
        });
        return updated;
      });
      
      toast.success('Progress saved');
    } catch (error) {
      toast.error('Failed to save progress');
      console.error(error);
    }
  };

  const handleSubmit = async () => {
    if (!diagnostic?.id) {
      toast.error('Diagnostic not loaded yet');
      return;
    }

    if (!user?.id) {
      toast.error('User not authenticated');
      return;
    }

    try {
      // Step 1: Save all responses first (complete user_responses)
      toast.info('Saving all responses...');
      await dispatch(updateDiagnosticResponses({
        diagnosticId: diagnostic.id,
        updates: {
          userResponses: responses,
          status: 'in_progress', // Keep as in_progress until submit completes
        },
      })).unwrap();

      // Step 2: Submit diagnostic to trigger LLM processing
      toast.info('Submitting diagnostic for AI analysis... This may take 10-15 minutes');
      await dispatch(submitDiagnostic({
        diagnosticId: diagnostic.id,
        completedByUserId: user.id,
      })).unwrap();
      
      toast.success('Diagnostic submitted successfully! AI is analyzing your responses...');
      
      // Clear local responses since everything is now saved and submitted
      setLocalResponses({});
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to submit diagnostic';
      toast.error(errorMessage);
      console.error('Submit error:', error);
    }
  };

  const handleNextPage = async () => {
    // Auto-save before moving to next page
    await handleSaveProgress();
    
    // If moving from first page (page 0) to second page, update engagement status to 'active'
    if (currentPage === 0 && !engagementStatusUpdated) {
      try {
        await dispatch(updateEngagement({
          id: engagementId,
          updates: {
            status: 'active', // Change from 'draft' to 'active' (in progress)
          },
        })).unwrap();
        setEngagementStatusUpdated(true);
      } catch (engagementError) {
        // Log error but don't fail the page navigation
        console.warn('Failed to update engagement status:', engagementError);
      }
    }
    
    if (currentPage < totalPages - 1) {
      // Mark current page as completed
      if (!completedPages.includes(currentPage)) {
        setCompletedPages([...completedPages, currentPage]);
      }
      setCurrentPage(currentPage + 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      // Last page - submit
      await handleSubmit();
    }
  };

  const handlePrevPage = () => {
    if (currentPage > 0) {
      setCurrentPage(currentPage - 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleResponseChange = (fieldName: string, value: any) => {
    // Update local state for immediate UI feedback
    setLocalResponses((prev) => ({
      ...prev,
      [fieldName]: value,
    }));
    
    // Also update Redux for optimistic update
    dispatch(updateLocalResponses({ [fieldName]: value }));
  };

  // Show loading state
  if (isLoading && !diagnostic) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="flex items-center justify-center py-12">
          <p className="text-muted-foreground">Loading diagnostic...</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (error && !diagnostic) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="text-center py-12">
          <p className="text-destructive mb-2">Error loading diagnostic</p>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  // Show message if diagnostic not found
  if (!diagnostic) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="text-center py-12">
          <p className="text-muted-foreground">No diagnostic found for this engagement.</p>
          <p className="text-sm text-muted-foreground mt-2">
            Please ensure the engagement has a diagnostic tool selected.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* If diagnostic is completed, show completion message and download button */}
      {diagnostic.status === 'completed' && (
        <div className="mb-8 rounded-lg border border-green-200 bg-green-50 p-4">
          <p className="font-semibold text-green-800">
            Diagnostic completed and analyzed.
          </p>
          <p className="mt-1 text-sm text-green-900">
            You can download the full diagnostic report as a PDF.
          </p>
          <div className="mt-4">
            <Button
              variant="default"
              onClick={async () => {
                try {
                  const token = localStorage.getItem('auth_token');
                  if (!token) {
                    toast.error('Not authenticated');
                    return;
                  }

                  const res = await fetch(
                    `${API_BASE_URL}/api/diagnostics/${diagnostic.id}/download`,
                    {
                      headers: {
                        Authorization: `Bearer ${token}`,
                      },
                    }
                  );

                  if (!res.ok) {
                    const errorText = await res.text();
                    toast.error(
                      `Failed to download report (${res.status}): ${errorText || 'Unexpected error'}`
                    );
                    return;
                  }

                  const blob = await res.blob();
                  const url = window.URL.createObjectURL(blob);

                  const disposition = res.headers.get('Content-Disposition') || '';
                  const match = disposition.match(/filename="(.+)"/);
                  const filename =
                    match?.[1] || `TrinityAi-diagnostic-${diagnostic.id}.pdf`;

                  const a = document.createElement('a');
                  a.href = url;
                  a.download = filename;
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  window.URL.revokeObjectURL(url);
                } catch (err) {
                  console.error('Download error', err);
                  toast.error('Failed to download diagnostic report');
                }
              }}
            >
              Download Diagnostic Summary
            </Button>
          </div>
        </div>
      )}

      {/* Progress Bar */}
  {!isSubmitting &&    <div className="mb-8">
        <div className="flex justify-between items-center mb-2">
          <h2 className="text-2xl font-bold">{currentPageData.title}</h2>
          <span className="text-sm text-muted-foreground">
            Page {currentPage + 1} of {totalPages}
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div 
            className="bg-accent h-2 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>}

      {isSubmitting ? (
        // Loading screen shown while submitting (replaces questions + buttons)
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <div className="h-12 w-12 rounded-full border-4 border-accent border-t-transparent animate-spin" />
          <p className="text-sm text-muted-foreground text-center max-w-md">
            Generating your AI report. This can take 10 -15 minutes. You can safely keep this tab open while we process your results.
          </p>
        </div>
      ) : (
        <>
          {/* Questions */}
          <div className="space-y-6">
            {currentPageData.elements.map((element) => {
              // Get value from merged responses (includes both saved and local changes)
              const value = responses[element.name];
              
              return (
                <ToolQuestion
                  key={element.name}
                  question={element}
                  value={value}
                  onChange={(value) => handleResponseChange(element.name, value)}
                  allResponses={responses}
                  diagnosticId={diagnostic?.id}
                />
              );
            })}
          </div>

          {/* Navigation */}
          <div className="flex justify-between mt-8">
            <Button
              variant="outline"
              onClick={handlePrevPage}
              disabled={currentPage === 0 || isSaving || isLoading}
            >
              Previous
            </Button>
            
            <Button onClick={handleNextPage} disabled={isSaving || isLoading || !diagnostic?.id}>
              {isSaving 
                ? 'Saving...' 
                : currentPage === totalPages - 1 
                ? 'Submit' 
                : 'Next'}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}