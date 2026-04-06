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
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-green-600" />
            Cross-Pattern Analysis Complete
          </CardTitle>
          <CardDescription>
            Review the synthesis below. Add notes or corrections, then approve to proceed to section drafting.
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Recurring Themes */}
      {themes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Lightbulb className="w-4 h-4" />
              Recurring Themes ({themes.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {themes.map((theme: any, i: number) => (
                <div key={i} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <h4 className="font-medium text-sm">{theme.theme}</h4>
                    <Badge variant="outline" className={SIGNAL_COLOURS[theme.signal_strength] || ''}>
                      {(theme.signal_strength || 'moderate').replace('_', ' ')}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{theme.description}</p>
                  {theme.sources && theme.sources.length > 0 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Sources: {theme.sources.join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tensions */}
      {tensions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Tensions & Contradictions ({tensions.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {tensions.map((t: any, i: number) => (
                <div key={i} className="border rounded-lg p-3">
                  <p className="text-sm font-medium">{t.tension || t.title}</p>
                  {t.description && <p className="text-sm text-muted-foreground mt-1">{t.description}</p>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Correlations */}
      {correlations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Link2 className="w-4 h-4" />
              Correlations ({correlations.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {correlations.map((c: any, i: number) => (
                <div key={i} className="border rounded-lg p-3">
                  <p className="text-sm">{c.correlation || c.description}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Data Gaps */}
      {gaps.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Zap className="w-4 h-4" />
              Data Gaps
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
              {gaps.map((gap: string, i: number) => (
                <li key={i}>{gap}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Preliminary Observations */}
      {observations.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <h4 className="font-medium text-sm mb-2">Preliminary Observations</h4>
            <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
              {observations.map((obs: string, i: number) => (
                <li key={i}>{obs}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Advisor Notes & Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Advisor Notes (optional)</CardTitle>
          <CardDescription>
            Add corrections, emphasis, or additional context before proceeding.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={advisorNotes}
            onChange={(e) => setAdvisorNotes(e.target.value)}
            placeholder="e.g. 'Emphasise the people capacity constraint' or 'The financial data needs to reflect FY25 projections'..."
            rows={3}
          />
          <div className="flex gap-3">
            <Button onClick={handleApprove} className="flex-1" size="lg">
              <ArrowRight className="w-4 h-4 mr-2" />
              Approve & Proceed to Section Drafting
            </Button>
            <Button variant="outline" onClick={handleRerun}>
              Re-run Analysis
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
