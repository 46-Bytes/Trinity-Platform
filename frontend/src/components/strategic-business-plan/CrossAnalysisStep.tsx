import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { triggerCrossAnalysis, saveCrossAnalysisNotes } from '@/store/slices/strategicBusinessPlanReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, CheckCircle2, AlertTriangle, ArrowRight, Lightbulb, Link2, Zap, Pencil, Plus, X, Save } from 'lucide-react';
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

const SIGNAL_OPTIONS = ['very_strong', 'strong', 'moderate'];

export function CrossAnalysisStep({ planId, onComplete }: CrossAnalysisStepProps) {
  const dispatch = useAppDispatch();
  const { currentPlan, isAnalysing } = useAppSelector((s) => s.strategicBusinessPlan);
  const [advisorNotes, setAdvisorNotes] = useState('');
  const [hasTriggered, setHasTriggered] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Local editable state
  const [editedThemes, setEditedThemes] = useState<any[]>([]);
  const [editedTensions, setEditedTensions] = useState<any[]>([]);
  const [editedCorrelations, setEditedCorrelations] = useState<any[]>([]);
  const [editedGaps, setEditedGaps] = useState<string[]>([]);
  const [editedObservations, setEditedObservations] = useState<string[]>([]);

  const crossAnalysis = currentPlan?.cross_analysis;

  useEffect(() => {
    if (!crossAnalysis && !hasTriggered && !isAnalysing) {
      setHasTriggered(true);
      dispatch(triggerCrossAnalysis({ planId }));
    }
  }, [crossAnalysis, hasTriggered, isAnalysing, planId, dispatch]);

  // Sync local state when crossAnalysis loads
  useEffect(() => {
    if (crossAnalysis && !isEditing) {
      setEditedThemes(crossAnalysis.recurring_themes || []);
      setEditedTensions(crossAnalysis.tensions || []);
      setEditedCorrelations(crossAnalysis.correlations || []);
      setEditedGaps(crossAnalysis.data_gaps || []);
      setEditedObservations(crossAnalysis.preliminary_observations || []);
    }
  }, [crossAnalysis, isEditing]);

  const handleApprove = async () => {
    if (advisorNotes.trim()) {
      await dispatch(saveCrossAnalysisNotes({ planId, notes: advisorNotes }));
    }
    toast.success('Cross-analysis approved. Proceeding to section drafting.');
    onComplete();
  };

  const handleRerun = () => {
    setHasTriggered(true);
    setIsEditing(false);
    dispatch(triggerCrossAnalysis({ planId, customInstructions: advisorNotes || undefined }));
  };

  const handleStartEdit = () => {
    setEditedThemes(crossAnalysis?.recurring_themes || []);
    setEditedTensions(crossAnalysis?.tensions || []);
    setEditedCorrelations(crossAnalysis?.correlations || []);
    setEditedGaps(crossAnalysis?.data_gaps || []);
    setEditedObservations(crossAnalysis?.preliminary_observations || []);
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
  };

  const handleSaveEdits = async () => {
    setIsSaving(true);
    try {
      const edited = {
        ...(crossAnalysis || {}),
        recurring_themes: editedThemes,
        tensions: editedTensions,
        correlations: editedCorrelations,
        data_gaps: editedGaps,
        preliminary_observations: editedObservations,
      };
      await dispatch(saveCrossAnalysisNotes({ planId, crossAnalysis: edited })).unwrap();
      setIsEditing(false);
      toast.success('Changes saved.');
    } catch {
      toast.error('Failed to save changes.');
    } finally {
      setIsSaving(false);
    }
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

  const themes = isEditing ? editedThemes : (crossAnalysis.recurring_themes || []);
  const tensions = isEditing ? editedTensions : (crossAnalysis.tensions || []);
  const correlations = isEditing ? editedCorrelations : (crossAnalysis.correlations || []);
  const gaps = isEditing ? editedGaps : (crossAnalysis.data_gaps || []);
  const observations = isEditing ? editedObservations : (crossAnalysis.preliminary_observations || []);

  return (
    <div className="space-y-4">
      {/* Summary card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <CheckCircle2 className="w-5 h-5 text-green-600" />
                Cross-Pattern Analysis Complete
              </CardTitle>
              <CardDescription className="text-sm mt-1">Review findings, then approve to proceed.</CardDescription>
            </div>
            {!isEditing ? (
              <Button variant="outline" size="sm" onClick={handleStartEdit}>
                <Pencil className="w-4 h-4 mr-1.5" />
                Edit
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleCancelEdit} disabled={isSaving}>
                  <X className="w-4 h-4 mr-1.5" />
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSaveEdits} disabled={isSaving}>
                  {isSaving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />}
                  Save
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-5">

          {/* Recurring Themes */}
          {(themes.length > 0 || isEditing) && (
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                <Lightbulb className="w-4 h-4" /> Themes
              </p>
              <div className="space-y-1.5">
                {themes.map((theme: any, i: number) => (
                  <div key={i} className="flex items-center justify-between gap-2 py-1.5 border-b last:border-0">
                    {isEditing ? (
                      <>
                        <Input
                          value={theme.theme}
                          onChange={(e) => {
                            const updated = [...editedThemes];
                            updated[i] = { ...updated[i], theme: e.target.value };
                            setEditedThemes(updated);
                          }}
                          className="flex-1 h-8 text-sm"
                        />
                        <Select
                          value={theme.signal_strength || 'moderate'}
                          onValueChange={(v) => {
                            const updated = [...editedThemes];
                            updated[i] = { ...updated[i], signal_strength: v };
                            setEditedThemes(updated);
                          }}
                        >
                          <SelectTrigger className="w-32 h-8 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {SIGNAL_OPTIONS.map((opt) => (
                              <SelectItem key={opt} value={opt} className="text-xs">
                                {opt.replace('_', ' ')}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <button
                          onClick={() => setEditedThemes(editedThemes.filter((_, idx) => idx !== i))}
                          className="text-muted-foreground hover:text-destructive flex-shrink-0"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <>
                        <span className="text-base">{theme.theme}</span>
                        <Badge variant="outline" className={`text-xs flex-shrink-0 ${SIGNAL_COLOURS[theme.signal_strength] || ''}`}>
                          {(theme.signal_strength || 'moderate').replace('_', ' ')}
                        </Badge>
                      </>
                    )}
                  </div>
                ))}
                {isEditing && (
                  <button
                    onClick={() => setEditedThemes([...editedThemes, { theme: '', signal_strength: 'moderate', description: '', sources: [] }])}
                    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mt-1"
                  >
                    <Plus className="w-4 h-4" /> Add theme
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Tensions */}
          {(tensions.length > 0 || isEditing) && (
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" /> Tensions
              </p>
              <ul className="space-y-1">
                {tensions.map((t: any, i: number) => (
                  <li key={i} className="flex items-center gap-2 py-1 border-b last:border-0">
                    {isEditing ? (
                      <>
                        <Input
                          value={t.tension || t.title || ''}
                          onChange={(e) => {
                            const updated = [...editedTensions];
                            updated[i] = { ...updated[i], tension: e.target.value, title: e.target.value };
                            setEditedTensions(updated);
                          }}
                          className="flex-1 h-8 text-sm"
                        />
                        <button
                          onClick={() => setEditedTensions(editedTensions.filter((_, idx) => idx !== i))}
                          className="text-muted-foreground hover:text-destructive flex-shrink-0"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <span className="text-base">{t.tension || t.title}</span>
                    )}
                  </li>
                ))}
                {isEditing && (
                  <button
                    onClick={() => setEditedTensions([...editedTensions, { tension: '', title: '' }])}
                    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mt-1"
                  >
                    <Plus className="w-4 h-4" /> Add tension
                  </button>
                )}
              </ul>
            </div>
          )}

          {/* Correlations */}
          {(correlations.length > 0 || isEditing) && (
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                <Link2 className="w-4 h-4" /> Correlations
              </p>
              <ul className="space-y-1">
                {correlations.map((c: any, i: number) => (
                  <li key={i} className="flex items-center gap-2 py-1 border-b last:border-0">
                    {isEditing ? (
                      <>
                        <Input
                          value={c.correlation || c.description || ''}
                          onChange={(e) => {
                            const updated = [...editedCorrelations];
                            updated[i] = { ...updated[i], correlation: e.target.value, description: e.target.value };
                            setEditedCorrelations(updated);
                          }}
                          className="flex-1 h-8 text-sm"
                        />
                        <button
                          onClick={() => setEditedCorrelations(editedCorrelations.filter((_, idx) => idx !== i))}
                          className="text-muted-foreground hover:text-destructive flex-shrink-0"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <span className="text-base">{c.correlation || c.description}</span>
                    )}
                  </li>
                ))}
                {isEditing && (
                  <button
                    onClick={() => setEditedCorrelations([...editedCorrelations, { correlation: '', description: '' }])}
                    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mt-1"
                  >
                    <Plus className="w-4 h-4" /> Add correlation
                  </button>
                )}
              </ul>
            </div>
          )}

          {/* Data Gaps */}
          {(gaps.length > 0 || isEditing) && (
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                <Zap className="w-4 h-4" /> Data Gaps
              </p>
              <ul className="space-y-1">
                {gaps.map((gap: string, i: number) => (
                  <li key={i} className="flex items-center gap-2 py-1 border-b last:border-0">
                    {isEditing ? (
                      <>
                        <Input
                          value={gap}
                          onChange={(e) => {
                            const updated = [...editedGaps];
                            updated[i] = e.target.value;
                            setEditedGaps(updated);
                          }}
                          className="flex-1 h-8 text-sm"
                        />
                        <button
                          onClick={() => setEditedGaps(editedGaps.filter((_, idx) => idx !== i))}
                          className="text-muted-foreground hover:text-destructive flex-shrink-0"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <span className="text-base text-muted-foreground">{gap}</span>
                    )}
                  </li>
                ))}
                {isEditing && (
                  <button
                    onClick={() => setEditedGaps([...editedGaps, ''])}
                    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mt-1"
                  >
                    <Plus className="w-4 h-4" /> Add data gap
                  </button>
                )}
              </ul>
            </div>
          )}

          {/* Preliminary Observations */}
          {(observations.length > 0 || isEditing) && (
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-2">Observations</p>
              <ul className="space-y-1">
                {observations.map((obs: string, i: number) => (
                  <li key={i} className="flex items-center gap-2 py-1 border-b last:border-0">
                    {isEditing ? (
                      <>
                        <Input
                          value={obs}
                          onChange={(e) => {
                            const updated = [...editedObservations];
                            updated[i] = e.target.value;
                            setEditedObservations(updated);
                          }}
                          className="flex-1 h-8 text-sm"
                        />
                        <button
                          onClick={() => setEditedObservations(editedObservations.filter((_, idx) => idx !== i))}
                          className="text-muted-foreground hover:text-destructive flex-shrink-0"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <span className="text-base text-muted-foreground">{obs}</span>
                    )}
                  </li>
                ))}
                {isEditing && (
                  <button
                    onClick={() => setEditedObservations([...editedObservations, ''])}
                    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mt-1"
                  >
                    <Plus className="w-4 h-4" /> Add observation
                  </button>
                )}
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
            <Button onClick={handleApprove} className="flex-1" disabled={isEditing}>
              <ArrowRight className="w-4 h-4 mr-2" />
              Approve & Proceed
            </Button>
            <Button variant="outline" onClick={handleRerun} disabled={isEditing}>
              Re-run
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
