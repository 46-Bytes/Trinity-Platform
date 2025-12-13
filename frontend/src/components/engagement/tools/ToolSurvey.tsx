import { useState, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { ToolQuestion } from './ToolQuestion';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  fetchDiagnosticByEngagement,
  updateDiagnosticResponses,
  updateLocalResponses,
} from '@/store/slices/diagnosticReducer';
import surveyData from '@/questions/diagnostic-survey.json';
import { toast } from 'sonner';

interface ToolSurveyProps {
  engagementId: string;
  toolType?: 'diagnostic'; // Can extend for other tools
}

export function ToolSurvey({ engagementId, toolType = 'diagnostic' }: ToolSurveyProps) {
  const dispatch = useAppDispatch();
  const { diagnostic, isSaving, isLoading, error } = useAppSelector((state) => state.diagnostic);
  
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
      const updatedDiagnostic = await dispatch(updateDiagnosticResponses({
        diagnosticId: diagnostic.id,
        updates: {
          userResponses: currentPageResponses,
          status: 'in_progress',
        },
      })).unwrap();
      
      // Clear local responses since they're now saved in Redux
      // The responses will come from Redux via useMemo
      setLocalResponses({});
      
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

    try {
      // Save all responses before submitting
      await dispatch(updateDiagnosticResponses({
        diagnosticId: diagnostic.id,
        updates: {
          userResponses: responses,
          status: 'completed',
        },
      })).unwrap();
      
      toast.success('Diagnostic submitted successfully! AI is analyzing your responses...');
    } catch (error) {
      toast.error('Failed to submit diagnostic');
      console.error(error);
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
          {isSaving ? 'Saving...' : currentPage === totalPages - 1 ? 'Submit' : 'Next'}
        </Button>
      </div>
    </div>
  );
}