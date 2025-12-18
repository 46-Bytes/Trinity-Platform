import { useState, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { CheckCircle2, Circle } from 'lucide-react';
import { ToolQuestion } from './ToolQuestion';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  fetchDiagnosticByEngagement,
  updateDiagnosticResponses,
  updateLocalResponses,
  submitDiagnostic,
} from '@/store/slices/diagnosticReducer';
import { useAuth } from '@/context/AuthContext';
import surveyData from '@/questions/diagnostic-survey.json';
import { toast } from 'sonner';

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
      toast.info('Submitting diagnostic for AI analysis... This may take 5-7 minutes.');
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

  const handlePageJump = async (pageIndex: number) => {
    // Don't jump if already on that page
    if (pageIndex === currentPage) {
      return;
    }
    
    // Auto-save before jumping to a different page
    if (diagnostic?.id) {
      await handleSaveProgress();
    }
    
    if (pageIndex >= 0 && pageIndex < totalPages) {
      // Mark current page as visited
      if (!completedPages.includes(currentPage)) {
        setCompletedPages([...completedPages, currentPage]);
      }
      setCurrentPage(pageIndex);
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
    <div className="flex gap-8 min-h-screen">
      {/* Vertical Stepper - Left Sidebar */}
      <div className="w-64 flex-shrink-0 border-r border-border pr-6 py-6 sticky top-0 h-fit max-h-screen overflow-y-auto">
        <div className="space-y-2">
          {pages.map((page, index) => {
            const isActive = index === currentPage;
            const isCompleted = completedPages.includes(index);
            const isPast = index < currentPage;
            
            return (
              <div key={index} className="relative">
                {/* Connector Line */}
                {index < totalPages - 1 && (
                  <div
                    className={cn(
                      "absolute left-4 top-8 w-0.5 h-full",
                      isPast || isCompleted ? "bg-primary" : "bg-border"
                    )}
                    style={{ height: 'calc(100% + 0.5rem)' }}
                  />
                )}
                
                {/* Step Content */}
                <button
                  onClick={() => handlePageJump(index)}
                  className={cn(
                    "relative flex items-start gap-3 w-full text-left p-3 rounded-lg transition-colors",
                    "hover:bg-accent/50",
                    isActive && "bg-accent",
                    !isActive && "cursor-pointer"
                  )}
                  disabled={isSaving || isLoading}
                >
                  {/* Step Icon */}
                  <div className={cn(
                    "flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center border-2 transition-colors",
                    isCompleted && "bg-primary border-primary text-primary-foreground",
                    isActive && !isCompleted && "border-primary bg-primary/10 text-primary",
                    !isActive && !isCompleted && "border-border bg-background"
                  )}>
                    {isCompleted ? (
                      <CheckCircle2 className="w-3 h-3" />
                    ) : (
                      <Circle className="w-3 h-3" />
                    )}
                  </div>
                  
                  {/* Step Label */}
                  <div className="flex-1 min-w-0 pt-0.5">
                    <div className={cn(
                      "text-sm font-medium",
                      isActive && "text-primary",
                      !isActive && "text-muted-foreground"
                    )}>
                      {page.title}
                    </div>
                  </div>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Content - Right Side */}
      <div className="flex-1 max-w-4xl p-6">
        {/* Progress Bar */}
        <div className="mb-8">
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
        </div>

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
        <div className="flex items-center justify-between mt-8">
          <Button
            variant="outline"
            onClick={handlePrevPage}
            disabled={currentPage === 0 || isSaving || isLoading}
          >
            Previous
          </Button>
          
          <Button onClick={handleNextPage} disabled={isSaving || isLoading || isSubmitting || !diagnostic?.id}>
            {isSubmitting 
              ? 'Submitting...' 
              : isSaving 
              ? 'Saving...' 
              : currentPage === totalPages - 1 
              ? 'Submit' 
              : 'Next'}
          </Button>
        </div>
      </div>
    </div>
  );
}