/**
 * Step 6: 12-Month Plan Component
 * Displays the detailed recommendations plan
 */
import React, { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle2, AlertCircle, ChevronDown, ChevronUp, RefreshCw, Calendar, Target, ListChecks, Users, TrendingUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Badge } from '@/components/ui/badge';
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
  const [tokensUsed, setTokensUsed] = useState(0);
  const [openItems, setOpenItems] = useState<number[]>([]);
  
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
      onLoadingStateChangeRef.current(isLoading || isGenerating);
    }
  }, [isLoading, isGenerating]);

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
      setTokensUsed(result.tokens_used || 0);
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
            {/* Token Usage */}
            {tokensUsed > 0 && (
              <p className="text-sm text-muted-foreground">
                Tokens used: {tokensUsed.toLocaleString()}
              </p>
            )}

            {/* Plan Notes */}
            {plan.plan_notes && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <h4 className="font-semibold mb-2">Notes on the 12-Month Recommendations Plan</h4>
                <p className="text-sm text-blue-800">{plan.plan_notes}</p>
              </div>
            )}

            {/* Recommendations */}
            <div className="space-y-4">
              {plan.recommendations?.map((rec, index) => (
                <Collapsible
                  key={index}
                  open={openItems.includes(index)}
                  onOpenChange={() => toggleItem(index)}
                >
                  <div className="border rounded-lg overflow-hidden">
                    <CollapsibleTrigger className="w-full">
                      <div className="flex items-center justify-between p-4 bg-muted/50 hover:bg-muted transition-colors">
                        <div className="flex items-center gap-4">
                          <span className="font-bold text-2xl text-primary">{rec.number}</span>
                          <div className="text-left">
                            <h4 className="font-semibold">{rec.title}</h4>
                            <Badge variant="outline" className="mt-1">
                              <Calendar className="w-3 h-3 mr-1" />
                              {rec.timing}
                            </Badge>
                          </div>
                        </div>
                        {openItems.includes(index) ? (
                          <ChevronUp className="w-5 h-5" />
                        ) : (
                          <ChevronDown className="w-5 h-5" />
                        )}
                      </div>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="p-4 space-y-6">
                        {/* Purpose */}
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <Target className="w-4 h-4 text-primary" />
                            <h5 className="font-semibold">Purpose</h5>
                          </div>
                          <p className="text-muted-foreground">{rec.purpose}</p>
                        </div>

                        {/* Key Objectives */}
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <ListChecks className="w-4 h-4 text-primary" />
                            <h5 className="font-semibold">Key Objectives</h5>
                          </div>
                          <ul className="list-disc pl-5 space-y-1">
                            {rec.key_objectives?.map((obj, i) => (
                              <li key={i} className="text-muted-foreground">{obj}</li>
                            ))}
                          </ul>
                        </div>

                        {/* Actions to Complete */}
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <CheckCircle2 className="w-4 h-4 text-primary" />
                            <h5 className="font-semibold">Actions to Complete</h5>
                          </div>
                          <ol className="list-decimal pl-5 space-y-1">
                            {rec.actions?.map((action, i) => (
                              <li key={i} className="text-muted-foreground">{action}</li>
                            ))}
                          </ol>
                        </div>

                        {/* BBA Support Outline */}
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <Users className="w-4 h-4 text-primary" />
                            <h5 className="font-semibold">BBA Support Outline</h5>
                          </div>
                          <p className="text-muted-foreground">{rec.bba_support}</p>
                        </div>

                        {/* Expected Outcomes */}
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <TrendingUp className="w-4 h-4 text-primary" />
                            <h5 className="font-semibold">Expected Outcomes</h5>
                          </div>
                          <ul className="list-disc pl-5 space-y-1">
                            {rec.expected_outcomes?.map((outcome, i) => (
                              <li key={i} className="text-muted-foreground">{outcome}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              ))}
            </div>

            {/* Action Buttons */}
            <div className="flex justify-between pt-4 border-t">
              <div className="flex gap-2">
                <Button variant="outline" onClick={onBack}>
                  Back
                </Button>
                <Button variant="outline" onClick={handleGenerate}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Regenerate
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
