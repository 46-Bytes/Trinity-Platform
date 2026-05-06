import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { triggerCrossAnalysis, saveCrossAnalysisNotes } from '@/store/slices/strategicBusinessPlanReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Loader2, CheckCircle2, AlertTriangle, ArrowRight, Lightbulb, Link2, Zap } from 'lucide-react';
import { toast } from 'sonner';

interface CrossAnalysisStepProps {
  planId: string;
  onComplete: () => void;
}

const SIGNAL_COLOURS: Record<string, string> = {
  very_strong: 'bg-red-100 text-red-800',
  strong: 'bg-orange-100 text-orange-800',
  moderate: 'bg-yellow-100 text-yellow-800',
};

export function CrossAnalysisStep({ planId, onComplete }: CrossAnalysisStepProps) {
  const dispatch = useAppDispatch();
  const { currentPlan, isAnalysing } = useAppSelector((s) => s.strategicBusinessPlan);
  const [advisorNotes, setAdvisorNotes] = useState('');
  const [hasTriggered, setHasTriggered] = useState(false);

  const crossAnalysis = currentPlan?.cross_analysis;

  useEffect(() => {
    if (!crossAnalysis && !hasTriggered && !isAnalysing) {
      setHasTriggered(true);
      dispatch(triggerCrossAnalysis({ planId }));
    }
  }, [crossAnalysis, hasTriggered, isAnalysing, planId, dispatch]);

  const handleApprove = async () => {
    if (advisorNotes.trim()) {
      await dispatch(saveCrossAnalysisNotes({ planId, notes: advisorNotes }));
    }
    toast.success('Cross-analysis approved. Proceeding to section drafting.');
    onComplete();
  };

  const handleRerun = () => {
    setHasTriggered(true);
    dispatch(triggerCrossAnalysis({ planId, customInstructions: advisorNotes || undefined }));
  };

  if (isAnalysing) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16">
          <Loader2 className="w-12 h-12 animate-spin text-primary mb-4" />
          <h3 className="text-lg font-semibold mb-2">Performing Cross-Pattern Analysis</h3>
          <p className="text-muted-foreground text-center max-w-md">
            Reviewing all uploaded materials to identify recurring themes, tensions, correlations, and strategic signals...
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!crossAnalysis) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">Waiting for analysis to begin...</p>
        </CardContent>
      </Card>
    );
  }

  const themes = crossAnalysis.recurring_themes || [];
  const tensions = crossAnalysis.tensions || [];
  const correlations = crossAnalysis.correlations || [];
  const gaps = crossAnalysis.data_gaps || [];
  const observations = crossAnalysis.preliminary_observations || [];

  return (
    <div className="space-y-4">
      {/* Summary card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <CheckCircle2 className="w-5 h-5 text-green-600" />
            Cross-Pattern Analysis Complete
          </CardTitle>
          <CardDescription className="text-sm">Review findings, then approve to proceed.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">

          {/* Recurring Themes */}
          {themes.length > 0 && (
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                <Lightbulb className="w-4 h-4" /> Themes
              </p>
              <div className="space-y-1.5">
                {themes.map((theme: any, i: number) => (
                  <div key={i} className="flex items-center justify-between gap-2 py-1.5 border-b last:border-0">
                    <span className="text-base">{theme.theme}</span>
                    <Badge variant="outline" className={`text-xs flex-shrink-0 ${SIGNAL_COLOURS[theme.signal_strength] || ''}`}>
                      {(theme.signal_strength || 'moderate').replace('_', ' ')}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tensions */}
          {tensions.length > 0 && (
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" /> Tensions
              </p>
              <ul className="space-y-1">
                {tensions.map((t: any, i: number) => (
                  <li key={i} className="text-base py-1 border-b last:border-0">{t.tension || t.title}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Correlations */}
          {correlations.length > 0 && (
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                <Link2 className="w-4 h-4" /> Correlations
              </p>
              <ul className="space-y-1">
                {correlations.map((c: any, i: number) => (
                  <li key={i} className="text-base py-1 border-b last:border-0">{c.correlation || c.description}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Data Gaps */}
          {gaps.length > 0 && (
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                <Zap className="w-4 h-4" /> Data Gaps
              </p>
              <ul className="space-y-1">
                {gaps.map((gap: string, i: number) => (
                  <li key={i} className="text-base py-1 border-b last:border-0 text-muted-foreground">{gap}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Preliminary Observations */}
          {observations.length > 0 && (
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-2">Observations</p>
              <ul className="space-y-1">
                {observations.map((obs: string, i: number) => (
                  <li key={i} className="text-base py-1 border-b last:border-0 text-muted-foreground">{obs}</li>
                ))}
              </ul>
            </div>
          )}

        </CardContent>
      </Card>

      {/* Advisor Notes & Actions */}
      <Card>
        <CardContent className="pt-5 space-y-3">
          <Textarea
            value={advisorNotes}
            onChange={(e) => setAdvisorNotes(e.target.value)}
            placeholder="Advisor notes (optional) — e.g. 'Emphasise people capacity' or 'Use FY25 projections'…"
            rows={2}
          />
          <div className="flex gap-3">
            <Button onClick={handleApprove} className="flex-1">
              <ArrowRight className="w-4 h-4 mr-2" />
              Approve & Proceed
            </Button>
            <Button variant="outline" onClick={handleRerun}>
              Re-run
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
