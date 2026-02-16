/**
 * Step 6: 12-Month Plan Component
 * Displays and edits the detailed recommendations plan (add/delete/edit recommendations).
 */
import React, { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle2, AlertCircle, ChevronDown, ChevronUp, RefreshCw, Calendar, Target, ListChecks, Users, TrendingUp, Plus, Trash2, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface Recommendation {
  number: number;
  title: string;
  timing: string;
  purpose: string;
  key_objectives: string[];
  actions: string[];
  bba_support: string;
  expected_outcomes: string[];
}

export interface TwelveMonthPlan {
  plan_notes: string;
  recommendations: Recommendation[];
  timeline_summary?: {
    title: string;
    rows: Array<{
      rec_number: number;
      recommendation: string;
      focus_area: string;
      timing: string;
      key_outcome: string;
    }>;
  };
}

interface TwelveMonthPlanStepProps {
  projectId: string;
  onComplete: (plan: TwelveMonthPlan) => void;
  onBack: () => void;
  className?: string;
  onLoadingStateChange?: (isLoading: boolean) => void;
}

export function TwelveMonthPlanStep({ projectId, onComplete, onBack, className, onLoadingStateChange }: TwelveMonthPlanStepProps) {
  const [plan, setPlan] = useState<TwelveMonthPlan | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openItems, setOpenItems] = useState<number[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('auth_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  // Use ref to store the callback to avoid infinite loops
  const onLoadingStateChangeRef = useRef(onLoadingStateChange);
  useEffect(() => {
    onLoadingStateChangeRef.current = onLoadingStateChange;
  }, [onLoadingStateChange]);

  // Load existing 12-month plan on mount
  useEffect(() => {
    const loadExistingData = async () => {
      setIsInitialLoading(true);
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}`, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          credentials: 'include',
        });

        if (response.ok) {
          const result = await response.json();
          const project = result.project;
          
          if (project?.twelve_month_plan) {
            const planData = project.twelve_month_plan;
            // Check if it's wrapped in a key or direct
            const actualPlan = planData.twelve_month_plan || planData;
            if (actualPlan && actualPlan.recommendations && Array.isArray(actualPlan.recommendations) && actualPlan.recommendations.length > 0) {
              setPlan(actualPlan);
              setOpenItems([0]);
            }
          }
        }
      } catch (err) {
        console.error('Failed to load existing 12-month plan:', err);
      } finally {
        setIsInitialLoading(false);
      }
    };

    if (projectId) {
      loadExistingData();
    }
  }, [projectId]);

  useEffect(() => {
    if (onLoadingStateChangeRef.current) {
      onLoadingStateChangeRef.current(isLoading || isGenerating || isSaving);
    }
  }, [isLoading, isGenerating, isSaving]);

  // Generate 12-month plan
  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step6/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to generate plan' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();
      const planData = result.twelve_month_plan || { plan_notes: '', recommendations: [] };
      setPlan(planData);
      // Open first item by default
      if (planData.recommendations?.length > 0) {
        setOpenItems([0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate plan');
    } finally {
      setIsGenerating(false);
    }
  };

  // Confirm and proceed
  const handleConfirm = async () => {
    if (!plan) return;
    setIsLoading(true);
    onComplete(plan);
    setIsLoading(false);
  };

  // Toggle recommendation open/closed
  const toggleItem = (index: number) => {
    setOpenItems((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const renumberRecommendations = (recs: Recommendation[]) =>
    recs.map((r, i) => ({ ...r, number: i + 1 }));

  const updatePlanNotes = (value: string) => {
    setPlan((p) => (p ? { ...p, plan_notes: value } : null));
  };

  const updateRec = (index: number, field: keyof Recommendation, value: string | string[]) => {
    setPlan((p) => {
      if (!p?.recommendations) return p;
      const next = [...p.recommendations];
      const rec = { ...next[index], [field]: value };
      next[index] = rec;
      return { ...p, recommendations: next };
    });
  };

  const addRecommendation = () => {
    setPlan((p) => {
      if (!p) return p;
      const recs = p.recommendations || [];
      const newRec: Recommendation = {
        number: recs.length + 1,
        title: '',
        timing: 'Month 1',
        purpose: '',
        key_objectives: [],
        actions: [],
        bba_support: '',
        expected_outcomes: [],
      };
      return { ...p, recommendations: renumberRecommendations([...recs, newRec]) };
    });
    setOpenItems((prev) => [...prev, (plan?.recommendations?.length ?? 0)]);
  };

  const deleteRecommendation = (index: number) => {
    if (!plan?.recommendations?.length || !window.confirm('Remove this recommendation from the 12-month plan?')) return;
    setPlan((p) => {
      if (!p?.recommendations) return p;
      const next = p.recommendations.filter((_, i) => i !== index);
      return { ...p, recommendations: renumberRecommendations(next) };
    });
    setOpenItems((prev) => prev.filter((i) => i !== index).map((i) => (i > index ? i - 1 : i)));
  };

  const savePlan = async () => {
    if (!plan) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step6/plan`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({
          plan_notes: plan.plan_notes ?? '',
          recommendations: plan.recommendations ?? [],
        }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Failed to save plan' }));
        throw new Error(err.detail || String(response.status));
      }
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save plan');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader>
        <CardTitle>Step 6: 12-Month Recommendations Plan</CardTitle>
        <CardDescription>
          Review the detailed recommendations with objectives, actions, and expected outcomes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Initial Loading State */}
        {isInitialLoading && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground">Loading existing 12-month plan...</p>
          </div>
        )}

        {/* Generate Button */}
        {!isInitialLoading && !plan && !isGenerating && (
          <div className="text-center py-8">
            <p className="text-muted-foreground mb-4">
              Click below to generate the 12-month recommendations plan.
            </p>
            <Button onClick={handleGenerate} size="lg">
              <RefreshCw className="w-4 h-4 mr-2" />
              Generate 12-Month Plan
            </Button>
          </div>
        )}

        {/* Loading State */}
        {isGenerating && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground">Generating 12-month plan...</p>
            <p className="text-sm text-muted-foreground mt-2">This may take a few minutes.</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <span className="text-red-700">{error}</span>
            <Button variant="outline" size="sm" onClick={handleGenerate} className="ml-auto">
              Retry
            </Button>
          </div>
        )}

        {/* Plan Content */}
        {!isInitialLoading && plan && (
          <>
            {saveError && (
              <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
                <AlertCircle className="w-5 h-5 text-red-500" />
                <span className="text-red-700">{saveError}</span>
                <button onClick={() => setSaveError(null)} className="ml-auto text-red-400 hover:text-red-600">×</button>
              </div>
            )}

            {/* Plan Notes (editable) */}
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <h4 className="font-semibold mb-2">Notes on the 12-Month Recommendations Plan</h4>
              <Textarea
                className="min-h-[80px] bg-white text-blue-800"
                value={plan.plan_notes ?? ''}
                onChange={(e) => updatePlanNotes(e.target.value)}
                placeholder="Add notes or context for the plan..."
              />
            </div>

            {/* Recommendations (editable, add/delete) */}
            <div className="space-y-4">
              {plan.recommendations?.map((rec, index) => (
                <Collapsible
                  key={index}
                  open={openItems.includes(index)}
                  onOpenChange={() => toggleItem(index)}
                >
                  <div className="border rounded-lg overflow-hidden">
                    <div className="flex items-center">
                      <CollapsibleTrigger className="flex-1">
                        <div className="flex items-center justify-between p-4 bg-muted/50 hover:bg-muted transition-colors w-full text-left">
                          <div className="flex items-center gap-4">
                            <span className="font-bold text-2xl text-primary">{rec.number}</span>
                            <div>
                              <h4 className="font-semibold">{rec.title || '(No title)'}</h4>
                              <Badge variant="outline" className="mt-1">
                                <Calendar className="w-3 h-3 mr-1" />
                                {rec.timing}
                              </Badge>
                            </div>
                          </div>
                          {openItems.includes(index) ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                        </div>
                      </CollapsibleTrigger>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="text-destructive hover:text-destructive shrink-0"
                        onClick={() => deleteRecommendation(index)}
                        title="Delete this recommendation"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                    <CollapsibleContent>
                      <div className="p-4 space-y-6 border-t">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <label className="text-sm font-medium mb-1 block">Title</label>
                            <Input
                              value={rec.title ?? ''}
                              onChange={(e) => updateRec(index, 'title', e.target.value)}
                              placeholder="Recommendation title"
                            />
                          </div>
                          <div>
                            <label className="text-sm font-medium mb-1 block">Timing</label>
                            <Input
                              value={rec.timing ?? ''}
                              onChange={(e) => updateRec(index, 'timing', e.target.value)}
                              placeholder="e.g. Month 1-2 or Feb–Mar 2026"
                            />
                          </div>
                        </div>

                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <Target className="w-4 h-4 text-primary" />
                            <h5 className="font-semibold">Purpose</h5>
                          </div>
                          <Textarea
                            className="min-h-[80px]"
                            value={rec.purpose ?? ''}
                            onChange={(e) => updateRec(index, 'purpose', e.target.value)}
                            placeholder="Purpose of this recommendation"
                          />
                        </div>

                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <ListChecks className="w-4 h-4 text-primary" />
                            <h5 className="font-semibold">Key Objectives</h5>
                          </div>
                          <ul className="space-y-2">
                            {(rec.key_objectives ?? []).map((obj, i) => (
                              <li key={i} className="flex gap-2">
                                <Input
                                  className="flex-1"
                                  value={obj}
                                  onChange={(e) => {
                                    const arr = [...(rec.key_objectives ?? [])];
                                    arr[i] = e.target.value;
                                    updateRec(index, 'key_objectives', arr);
                                  }}
                                />
                                <Button type="button" variant="ghost" size="sm" className="text-destructive shrink-0" onClick={() => updateRec(index, 'key_objectives', (rec.key_objectives ?? []).filter((_, j) => j !== i))}>Remove</Button>
                              </li>
                            ))}
                            <li>
                              <Button type="button" variant="outline" size="sm" onClick={() => updateRec(index, 'key_objectives', [...(rec.key_objectives ?? []), ''])}>
                                <Plus className="w-4 h-4 mr-1" /> Add objective
                              </Button>
                            </li>
                          </ul>
                        </div>

                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <CheckCircle2 className="w-4 h-4 text-primary" />
                            <h5 className="font-semibold">Actions to Complete</h5>
                          </div>
                          <ul className="space-y-2">
                            {(rec.actions ?? []).map((action, i) => (
                              <li key={i} className="flex gap-2">
                                <Input
                                  className="flex-1"
                                  value={action}
                                  onChange={(e) => {
                                    const arr = [...(rec.actions ?? [])];
                                    arr[i] = e.target.value;
                                    updateRec(index, 'actions', arr);
                                  }}
                                />
                                <Button type="button" variant="ghost" size="sm" className="text-destructive shrink-0" onClick={() => updateRec(index, 'actions', (rec.actions ?? []).filter((_, j) => j !== i))}>Remove</Button>
                              </li>
                            ))}
                            <li>
                              <Button type="button" variant="outline" size="sm" onClick={() => updateRec(index, 'actions', [...(rec.actions ?? []), ''])}>
                                <Plus className="w-4 h-4 mr-1" /> Add action
                              </Button>
                            </li>
                          </ul>
                        </div>

                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <Users className="w-4 h-4 text-primary" />
                            <h5 className="font-semibold">BBA Support Outline</h5>
                          </div>
                          <Textarea
                            className="min-h-[80px]"
                            value={rec.bba_support ?? ''}
                            onChange={(e) => updateRec(index, 'bba_support', e.target.value)}
                            placeholder="BBA support outline"
                          />
                        </div>

                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <TrendingUp className="w-4 h-4 text-primary" />
                            <h5 className="font-semibold">Expected Outcomes</h5>
                          </div>
                          <ul className="space-y-2">
                            {(rec.expected_outcomes ?? []).map((outcome, i) => (
                              <li key={i} className="flex gap-2">
                                <Input
                                  className="flex-1"
                                  value={outcome}
                                  onChange={(e) => {
                                    const arr = [...(rec.expected_outcomes ?? [])];
                                    arr[i] = e.target.value;
                                    updateRec(index, 'expected_outcomes', arr);
                                  }}
                                />
                                <Button type="button" variant="ghost" size="sm" className="text-destructive shrink-0" onClick={() => updateRec(index, 'expected_outcomes', (rec.expected_outcomes ?? []).filter((_, j) => j !== i))}>Remove</Button>
                              </li>
                            ))}
                            <li>
                              <Button type="button" variant="outline" size="sm" onClick={() => updateRec(index, 'expected_outcomes', [...(rec.expected_outcomes ?? []), ''])}>
                                <Plus className="w-4 h-4 mr-1" /> Add outcome
                              </Button>
                            </li>
                          </ul>
                        </div>
                      </div>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              ))}

              <Button type="button" variant="outline" className="w-full" onClick={addRecommendation}>
                <Plus className="w-4 h-4 mr-2" />
                Add recommendation
              </Button>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t">
              <div className="flex gap-2">
                <Button variant="outline" onClick={onBack}>
                  Back
                </Button>
                <Button variant="outline" onClick={handleGenerate}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Regenerate
                </Button>
                <Button variant="secondary" onClick={savePlan} disabled={isSaving}>
                  {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                  Save changes
                </Button>
              </div>
              <Button onClick={handleConfirm} disabled={isLoading || !plan}>
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Continue to Review
                  </>
                )}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
