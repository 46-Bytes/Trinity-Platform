import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  initialiseSections,
  surfaceThemes,
  reorderSections,
} from '@/store/slices/strategicBusinessPlanReducer';
import { SectionSidebar } from './SectionSidebar';
import { SectionEditor } from './SectionEditor';
import { PLAN_SECTIONS } from './sectionConfig';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArrowRight, Lightbulb, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

interface SectionDraftingStepProps {
  planId: string;
  onComplete: () => void;
}

export function SectionDraftingStep({ planId, onComplete }: SectionDraftingStepProps) {
  const dispatch = useAppDispatch();
  const { currentPlan, isLoading, isDraftingSection } = useAppSelector((s) => s.strategicBusinessPlan);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [themesShown, setThemesShown] = useState(false);

  const sections = currentPlan?.sections || [];

  // Initialise sections if not done yet
  useEffect(() => {
    if (currentPlan && (!currentPlan.sections || currentPlan.sections.length === 0)) {
      dispatch(initialiseSections(planId));
    }
  }, [currentPlan, planId, dispatch]);

  // Restore position from backend
  useEffect(() => {
    if (currentPlan?.current_section_index !== null && currentPlan?.current_section_index !== undefined) {
      setCurrentIndex(currentPlan.current_section_index);
    }
  }, [currentPlan?.current_section_index]);

  const currentSection = sections[currentIndex];

  // Surface emerging themes after external_internal_analysis is approved
  useEffect(() => {
    if (!themesShown && sections.length > 0) {
      const externalAnalysis = sections.find((s) => s.key === 'external_internal_analysis');
      if (externalAnalysis?.status === 'approved' && !currentPlan?.emerging_themes) {
        dispatch(surfaceThemes(planId));
        setThemesShown(true);
      }
    }
  }, [sections, themesShown, currentPlan?.emerging_themes, planId, dispatch]);

  const handleNext = () => {
    if (currentIndex < sections.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handleSelect = (index: number) => {
    setCurrentIndex(index);
  };

  const handleReorder = async (fromIndex: number, toIndex: number) => {
    if (toIndex < 0 || toIndex >= sections.length) return;

    const newOrder = [...sections];
    const [moved] = newOrder.splice(fromIndex, 1);
    newOrder.splice(toIndex, 0, moved);

    // Optimistically update the displayed index
    if (currentIndex === fromIndex) {
      setCurrentIndex(toIndex);
    } else if (fromIndex < currentIndex && toIndex >= currentIndex) {
      setCurrentIndex(currentIndex - 1);
    } else if (fromIndex > currentIndex && toIndex <= currentIndex) {
      setCurrentIndex(currentIndex + 1);
    }

    await dispatch(reorderSections({ planId, sectionOrder: newOrder.map((s) => s.key) }));
  };

  // A required section is "done" if it's approved or skipped
  const requiredSections = PLAN_SECTIONS.filter((s) => s.required);
  const allRequiredDone = requiredSections.every((config) => {
    const section = sections.find((s) => s.key === config.key);
    return section?.status === 'approved' || section?.status === 'skipped';
  });

  const approvedRequiredCount = requiredSections.filter((config) => {
    const section = sections.find((s) => s.key === config.key);
    return section?.status === 'approved';
  }).length;

  const handleProceed = () => {
    if (!allRequiredDone) {
      toast.error('All required sections must be approved or skipped before proceeding.');
      return;
    }
    onComplete();
  };

  if (isLoading || sections.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16">
          <Loader2 className="w-10 h-10 animate-spin text-primary mb-4" />
          <p className="text-muted-foreground">Initialising plan sections...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Emerging Themes (shown after external_internal_analysis is approved) */}
      {currentPlan?.emerging_themes && currentIndex >= 4 && (
        <Card className="border-blue-200 bg-blue-50/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Lightbulb className="w-4 h-4 text-blue-600" />
              Emerging Strategic Themes
            </CardTitle>
            <CardDescription>
              Themes surfaced from the core diagnostic sections — these will inform the remaining sections.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {(currentPlan.emerging_themes.themes || []).map((theme: any, i: number) => (
                <Badge key={i} variant="secondary" className="py-1 px-3">
                  {theme.theme}
                </Badge>
              ))}
            </div>
            {currentPlan.emerging_themes.summary && (
              <p className="text-sm text-muted-foreground mt-3">{currentPlan.emerging_themes.summary}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Main drafting area */}
      <div className="flex border rounded-lg bg-background min-h-[600px]">
        <SectionSidebar
          sections={sections}
          currentIndex={currentIndex}
          onSelect={handleSelect}
          onReorder={handleReorder}
          isDisabled={isDraftingSection}
        />
        <div className="flex-1 p-6 overflow-y-auto">
          {currentSection && (
            <SectionEditor
              planId={planId}
              section={currentSection}
              sectionIndex={currentIndex}
              totalSections={sections.length}
              onNext={handleNext}
              onSkip={handleNext}
            />
          )}
        </div>
      </div>

      {/* Proceed button */}
      <div className="flex justify-end">
        <Button onClick={handleProceed} disabled={!allRequiredDone} size="lg">
          <ArrowRight className="w-4 h-4 mr-2" />
          Proceed to Plan Assembly
          {!allRequiredDone && (
            <span className="ml-2 text-xs opacity-70">
              ({approvedRequiredCount}/{requiredSections.length} required approved)
            </span>
          )}
        </Button>
      </div>
    </div>
  );
}
