import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ToolQuestion } from './ToolQuestion';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  saveToolProgress,
  submitTool,
} from '@/store/slices/toolReducer';
import surveyData from '@/questions/diagnostic-survey.json';
import { toast } from 'sonner';

interface ToolSurveyProps {
  engagementId: string;
  toolType?: 'diagnostic'; // Can extend for other tools
}

export function ToolSurvey({ engagementId, toolType = 'diagnostic' }: ToolSurveyProps) {
  const dispatch = useAppDispatch();
  const { isSaving, isSubmitting } = useAppSelector((state) => state.tool);
  
  const [currentPage, setCurrentPage] = useState(0);
  const [responses, setResponses] = useState<Record<string, any>>({});
  const [completedPages, setCompletedPages] = useState<number[]>([]);
  
  const pages = surveyData.pages;
  const totalPages = pages.length;
  const currentPageData = pages[currentPage];
  const progress = ((currentPage + 1) / totalPages) * 100;

  const handleSaveProgress = async () => {
    try {
      await dispatch(saveToolProgress({
        engagementId,
        toolType,
        responses,
        currentPage,
        completedPages,
      })).unwrap();
      
      toast.success('Progress saved');
    } catch (error) {
      toast.error('Failed to save progress');
      console.error(error);
    }
  };

  const handleSubmit = async () => {
    try {
      await dispatch(submitTool({
        engagementId,
        toolType,
        responses,
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
    setResponses({ ...responses, [fieldName]: value });
  };

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
        {currentPageData.elements.map((element) => (
          <ToolQuestion
            key={element.name}
            question={element}
            value={responses[element.name]}
            onChange={(value) => handleResponseChange(element.name, value)}
            allResponses={responses}
          />
        ))}
      </div>

      {/* Navigation */}
      <div className="flex justify-between mt-8">
        <Button
          variant="outline"
          onClick={handlePrevPage}
          disabled={currentPage === 0 || isSubmitting}
        >
          Previous
        </Button>
        
        <Button onClick={handleNextPage} disabled={isSubmitting}>
          {isSubmitting ? 'Submitting...' : currentPage === totalPages - 1 ? 'Submit' : 'Next'}
        </Button>
      </div>
    </div>
  );
}