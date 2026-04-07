import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { initialiseSections, surfaceThemes, getPlan } from '@/store/slices/strategicBusinessPlanReducer';
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

  // Check if we should surface emerging themes (after section 4 - external_internal_analysis)
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

  const handleSkip = () => {
    const config = PLAN_SECTIONS.find((c) => c.key === sections[currentIndex]?.key);
    if (!config?.required) {
      if (currentIndex < sections.length - 1) {
        handleNext();
      } else {
        toast.info('All sections complete — click "Proceed to Plan Assembly" to continue.');
      }
    }
  };

  const handleSelect = (index: number) => {
    setCurrentIndex(index);
  };

  // Check if all required sections are approved
  const requiredSections = PLAN_SECTIONS.filter((s) => s.required);
  const allRequiredApproved = requiredSections.every((config) => {
    const section = sections.find((s) => s.key === config.key);
    return section?.status === 'approved';
  });

  const handleProceed = () => {
    if (!allRequiredApproved) {
      toast.error('All required sections must be approved before proceeding.');
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

  // Show emerging themes card between section 4 and 5
  const showThemesCard =
    currentPlan?.emerging_themes &&
    currentIndex >= 4 && // After external_internal_analysis
    !themesShown;

  return (
    <div className="space-y-4">
      {/* Emerging Themes (shown after section 4 is approved) */}
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
              onSkip={handleSkip}
            />
          )}
        </div>
      </div>

      {/* Proceed button */}
      <div className="flex justify-end">
        <Button onClick={handleProceed} disabled={!allRequiredApproved} size="lg">
          <ArrowRight className="w-4 h-4 mr-2" />
          Proceed to Plan Assembly
          {!allRequiredApproved && (
            <span className="ml-2 text-xs opacity-70">
              ({requiredSections.filter((c) => sections.find((s) => s.key === c.key)?.status === 'approved').length}/{requiredSections.length} approved)
            </span>
          )}
        </Button>
      </div>
    </div>
  );
}
