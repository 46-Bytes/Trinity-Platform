import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { assemblePlan } from '@/store/slices/strategicBusinessPlanReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, CheckCircle2, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

interface PlanAssemblyStepProps {
  planId: string;
  onComplete: () => void;
}

export function PlanAssemblyStep({ planId, onComplete }: PlanAssemblyStepProps) {
  const dispatch = useAppDispatch();
  const { currentPlan, isLoading } = useAppSelector((s) => s.strategicBusinessPlan);

  const finalPlan = currentPlan?.final_plan;

  // Always re-assemble on mount so any section reordering from step 3 is reflected.
  // Assembly is fast (no AI calls) — passing the current section order ensures the
  // backend uses the latest order even if the user navigated back and reordered.
  useEffect(() => {
    const sectionOrder = currentPlan?.sections?.map((s) => s.key);
    dispatch(assemblePlan({ planId, sectionOrder }));
  }, [planId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading && !finalPlan) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16">
          <Loader2 className="w-10 h-10 animate-spin text-primary mb-4" />
          <p className="text-muted-foreground">Assembling your Strategic Business Plan...</p>
        </CardContent>
      </Card>
    );
  }

  if (!finalPlan) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">Waiting for plan assembly...</p>
          <Button className="mt-4" onClick={() => dispatch(assemblePlan({ planId, sectionOrder: currentPlan?.sections?.map((s) => s.key) }))}>
            Assemble Plan
          </Button>
        </CardContent>
      </Card>
    );
  }

  const sections = finalPlan.sections || [];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-600" />
                Plan Assembled
              </CardTitle>
              <CardDescription>
                Review the complete plan below. When satisfied, proceed to export.
              </CardDescription>
            </div>
            <Badge variant="outline" className="bg-green-100 text-green-800">
              {sections.filter((s: any) => s.status === 'approved').length} sections
            </Badge>
          </div>
        </CardHeader>
      </Card>

      {/* Table of Contents */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Table of Contents</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="list-decimal list-inside space-y-1 text-sm">
            {sections.map((section: any, i: number) => (
              <li key={section.key}>
                <a href={`#section-${section.key}`} className="text-primary hover:underline">
                  {section.title}
                </a>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      {/* Full Plan Preview */}
      {sections.map((section: any, i: number) => (
        <Card key={section.key} id={`section-${section.key}`}>
          <CardHeader>
            <CardTitle className="text-base">
              {i + 1}. {section.title}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="prose prose-sm max-w-none sbp-content"
              dangerouslySetInnerHTML={{ __html: section.content || '<p class="text-muted-foreground">No content</p>' }}
            />
            {section.strategic_implications && (
              <div className="border-t pt-4 mt-4">
                <h4 className="font-semibold text-sm mb-2">Strategic Implications</h4>
                <div
                  className="prose prose-sm max-w-none sbp-content"
                  dangerouslySetInnerHTML={{ __html: section.strategic_implications }}
                />
              </div>
            )}
          </CardContent>
        </Card>
      ))}

      <div className="flex justify-end">
        <Button onClick={onComplete} size="lg">
          <ArrowRight className="w-4 h-4 mr-2" />
          Proceed to Export
        </Button>
      </div>
    </div>
  );
}
