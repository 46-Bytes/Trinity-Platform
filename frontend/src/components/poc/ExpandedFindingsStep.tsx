/**
 * Step 4: Expanded Findings Component
 * Displays expanded findings with full paragraphs for each finding
 */
import React, { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Pencil, Save, X, RefreshCw, ChevronDown, ChevronUp, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface ExpandedFinding {
  rank: number;
  title: string;
  priority_area: string;
  paragraphs: string[];
  key_points?: string[];
}

interface ExpandedFindingsStepProps {
  projectId: string;
  onComplete: (expandedFindings: ExpandedFinding[]) => void;
  onBack: () => void;
  className?: string;
  onLoadingStateChange?: (isLoading: boolean) => void;
  initialData?: Record<string, any> | null;
  onDataChange?: () => void;
}

export function ExpandedFindingsStep({ projectId, onComplete, onBack, className, onLoadingStateChange, initialData, onDataChange }: ExpandedFindingsStepProps) {
  const [expandedFindings, setExpandedFindings] = useState<ExpandedFinding[]>([]);
  const [downstreamSnapshotRows, setDownstreamSnapshotRows] = useState<any[]>([]);
  const [downstreamPlanRecs, setDownstreamPlanRecs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<ExpandedFinding | null>(null);
  const [openItems, setOpenItems] = useState<number[]>([]);
  const [pendingDeleteIndex, setPendingDeleteIndex] = useState<number | null>(null);
  
  // Use ref to store the callback to avoid infinite loops
  const onLoadingStateChangeRef = useRef(onLoadingStateChange);
  useEffect(() => {
    onLoadingStateChangeRef.current = onLoadingStateChange;
  }, [onLoadingStateChange]);

  // Track whether initial data has been applied so that a cache refresh
  // triggered by persistExpandedFindings doesn't overwrite in-progress edits
  const hasInitialized = useRef(false);

  // Load existing expanded findings on mount — use cached data if available
  useEffect(() => {
    if (hasInitialized.current) return;

    const applyProject = (project: any) => {
      if (project?.expanded_findings) {
        const findingsData = project.expanded_findings.expanded_findings ||
          (Array.isArray(project.expanded_findings) ? project.expanded_findings : []);
        if (findingsData.length > 0) {
          setExpandedFindings(findingsData);
          setOpenItems(findingsData.map((_: any, i: number) => i));
        }
      }
    };

    if (initialData?.expanded_findings) {
      applyProject(initialData);
      const snapshotRows = (initialData.snapshot_table?.snapshot_table ?? initialData.snapshot_table)?.rows ?? [];
      if (snapshotRows.length > 0) setDownstreamSnapshotRows(snapshotRows);
      const rawPlan = initialData.twelve_month_plan;
      const planRecs = (rawPlan?.twelve_month_plan ?? rawPlan)?.recommendations ?? [];
      if (planRecs.length > 0) setDownstreamPlanRecs(planRecs);
      setIsInitialLoading(false);
      hasInitialized.current = true;
      return;
    }

    const loadExistingData = async () => {
      setIsInitialLoading(true);
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}`, {
          headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          credentials: 'include',
        });
        if (response.ok) {
          const result = await response.json();
          applyProject(result.project);
        }
      } catch (err) {
        console.error('Failed to load existing expanded findings:', err);
      } finally {
        setIsInitialLoading(false);
        hasInitialized.current = true;
      }
    };

    if (projectId) {
      loadExistingData();
    }
  }, [projectId, initialData]);

  // Notify parent of loading state changes (only for processing states, not initial load)
  useEffect(() => {
    if (onLoadingStateChangeRef.current) {
      onLoadingStateChangeRef.current(isLoading || isGenerating);
    }
  }, [isLoading, isGenerating]);

  // Generate expanded findings
  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step4/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to expand findings' }));
        const detail = errorData.detail || '';
        if (response.status === 401) {
          throw new Error('Your session has expired. Please save your work, log in again, and retry.');
        } else if (response.status === 400 && /draft findings/i.test(detail)) {
          throw new Error('Draft findings have not been generated yet. Please go back to Step 3.');
        } else if (response.status >= 500) {
          throw new Error('An error occurred while expanding findings. This may be due to a timeout or service issue. Please try again.');
        } else {
          throw new Error(detail || `HTTP ${response.status}`);
        }
      }

      const result = await response.json();
      const findingsData = result.expanded_findings?.expanded_findings || result.expanded_findings || [];
      setExpandedFindings(findingsData);
      // Open all items by default
      setOpenItems(findingsData.map((_: any, i: number) => i));
      onDataChange?.();
    } catch (err) {
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        setError('Network error. Please check your connection and try again.');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to expand findings');
      }
    } finally {
      setIsGenerating(false);
    }
  };

  // Confirm and proceed
  const handleConfirm = async () => {
    setIsLoading(true);
    onComplete(expandedFindings);
    setIsLoading(false);
  };

  // Toggle item open/closed
  const toggleItem = (index: number) => {
    setOpenItems((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  // Start editing
  const startEdit = (index: number) => {
    setEditingIndex(index);
    setEditForm({ ...expandedFindings[index] });
  };

  // Persist expanded findings edits to backend (non-blocking)
  const persistExpandedFindings = (updatedFindings: ExpandedFinding[]) => {
    const token = localStorage.getItem('auth_token');
    fetch(`${API_BASE_URL}/api/poc/${projectId}/step4/save`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      credentials: 'include',
      body: JSON.stringify({ expanded_findings: updatedFindings }),
    })
      .then(() => onDataChange?.())
      .catch((err) => console.error('Failed to auto-save expanded findings:', err));
  };

  // Save edit
  const saveEdit = () => {
    if (editingIndex !== null && editForm) {
      const updated = [...expandedFindings];
      updated[editingIndex] = editForm;
      setExpandedFindings(updated);
      setEditingIndex(null);
      setEditForm(null);
      persistExpandedFindings(updated);
    }
  };

  // Cancel edit
  const cancelEdit = () => {
    setEditingIndex(null);
    setEditForm(null);
  };

  // Update paragraph
  const updateParagraph = (paragraphIndex: number, value: string) => {
    if (editForm) {
      const updated = [...editForm.paragraphs];
      updated[paragraphIndex] = value;
      setEditForm({ ...editForm, paragraphs: updated });
    }
  };

  const persistDownstreamSnapshot = (rows: any[]) => {
    const token = localStorage.getItem('auth_token');
    fetch(`${API_BASE_URL}/api/poc/${projectId}/step5/save`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      credentials: 'include',
      body: JSON.stringify({ rows }),
    }).catch((err) => console.error('Failed to sync snapshot table order:', err));
  };

  const persistDownstreamPlan = (recs: any[]) => {
    const token = localStorage.getItem('auth_token');
    const rawPlan = initialData?.twelve_month_plan;
    const actualPlan = rawPlan?.twelve_month_plan ?? rawPlan ?? {};
    fetch(`${API_BASE_URL}/api/poc/${projectId}/step6/plan`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      credentials: 'include',
      body: JSON.stringify({ plan_notes: actualPlan.plan_notes ?? '', recommendations: recs }),
    }).catch((err) => console.error('Failed to sync plan order:', err));
  };

  const moveExpanded = (index: number, direction: 'up' | 'down') => {
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= expandedFindings.length) return;

    const updated = [...expandedFindings];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    updated.forEach((f, i) => (f.rank = i + 1));
    setExpandedFindings(updated);
    setOpenItems((prev) => prev.map((i) => (i === index ? newIndex : i === newIndex ? index : i)));
    persistExpandedFindings(updated);

    if (downstreamSnapshotRows.length > Math.max(index, newIndex)) {
      const newRows = [...downstreamSnapshotRows];
      [newRows[index], newRows[newIndex]] = [newRows[newIndex], newRows[index]];
      newRows.forEach((r: any, i: number) => (r.rank = i + 1));
      setDownstreamSnapshotRows(newRows);
      persistDownstreamSnapshot(newRows);
    }
    if (downstreamPlanRecs.length > Math.max(index, newIndex)) {
      const newRecs = [...downstreamPlanRecs];
      [newRecs[index], newRecs[newIndex]] = [newRecs[newIndex], newRecs[index]];
      newRecs.forEach((r: any, i: number) => (r.number = i + 1));
      setDownstreamPlanRecs(newRecs);
      persistDownstreamPlan(newRecs);
    }
  };

  // Delete finding — opens confirmation dialog
  const deleteFinding = (index: number) => {
    setPendingDeleteIndex(index);
  };

  const confirmDeleteFinding = () => {
    if (pendingDeleteIndex === null) return;
    const index = pendingDeleteIndex;
    const updated = expandedFindings.filter((_, i) => i !== index);
    updated.forEach((f, i) => (f.rank = i + 1));
    setExpandedFindings(updated);
    persistExpandedFindings(updated);
    setOpenItems((prev) => prev.filter((i) => i !== index).map((i) => (i > index ? i - 1 : i)));
    setPendingDeleteIndex(null);
  };

  // Add a new blank expanded finding
  const addFinding = () => {
    const newFinding: ExpandedFinding = {
      rank: expandedFindings.length + 1,
      title: '',
      priority_area: '',
      paragraphs: [''],
      key_points: [],
    };
    const newIndex = expandedFindings.length;
    setExpandedFindings([...expandedFindings, newFinding]);
    setOpenItems((prev) => [...prev, newIndex]);
    setEditingIndex(newIndex);
    setEditForm({ ...newFinding });
  };

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader>
        <CardTitle>Step 4: Expanded Findings</CardTitle>
        <CardDescription>
          Review the detailed explanations for each finding. Edit as needed before continuing.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Initial loading spinner */}
        {isInitialLoading && (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Loading expanded findings...</p>
          </div>
        )}

        {/* Generate Button */}
        {!isInitialLoading && expandedFindings.length === 0 && !isGenerating && (
          <div className="text-center py-8">
            <p className="text-muted-foreground mb-4">
              Click below to expand each finding into detailed paragraphs.
            </p>
            <Button onClick={handleGenerate} size="lg">
              <RefreshCw className="w-4 h-4 mr-2" />
              Expand Findings
            </Button>
          </div>
        )}

        {/* Loading State */}
        {isGenerating && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground">Expanding findings into detailed paragraphs...</p>
            <p className="text-sm text-muted-foreground mt-2">This may take a minute or two.</p>
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

        {/* Expanded Findings List */}
        {!isInitialLoading && !isGenerating && expandedFindings.length > 0 && (
          <>
            {/* Findings */}
            <div className="space-y-4">
              {expandedFindings.map((finding, index) => (
                <Collapsible
                  key={index}
                  open={openItems.includes(index)}
                  onOpenChange={() => toggleItem(index)}
                >
                  <div className="border rounded-lg overflow-hidden">
                    <CollapsibleTrigger className="w-full">
                      <div className="flex items-center justify-between p-4 bg-muted/50 hover:bg-muted transition-colors">
                        <div className="flex items-center gap-3">
                          <span className="font-bold text-xl text-primary">{finding.rank}</span>
                          <div className="text-left">
                            <h4 className="font-semibold">{finding.title}</h4>
                            <p className="text-sm text-muted-foreground">{finding.priority_area}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {editingIndex !== index && (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={index === 0}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  moveExpanded(index, 'up');
                                }}
                              >
                                <ChevronUp className="w-4 h-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={index === expandedFindings.length - 1}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  moveExpanded(index, 'down');
                                }}
                              >
                                <ChevronDown className="w-4 h-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  startEdit(index);
                                }}
                              >
                                <Pencil className="w-4 h-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  deleteFinding(index);
                                }}
                                className="text-red-500 hover:text-red-700"
                              >
                                <X className="w-4 h-4" />
                              </Button>
                            </>
                          )}
                          {openItems.includes(index) ? (
                            <ChevronUp className="w-5 h-5" />
                          ) : (
                            <ChevronDown className="w-5 h-5" />
                          )}
                        </div>
                      </div>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="p-4 space-y-4">
                        {editingIndex === index && editForm ? (
                          // Edit Mode
                          <div className="space-y-4">
                            <div>
                              <label className="text-sm font-medium">Title</label>
                              <Input
                                value={editForm.title}
                                onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                              />
                            </div>
                            <div>
                              <label className="text-sm font-medium">Priority Area</label>
                              <Input
                                value={editForm.priority_area}
                                onChange={(e) => setEditForm({ ...editForm, priority_area: e.target.value })}
                              />
                            </div>
                            {editForm.paragraphs.map((para, pIndex) => (
                              <div key={pIndex}>
                                <label className="text-sm font-medium">Paragraph {pIndex + 1}</label>
                                <Textarea
                                  value={para}
                                  onChange={(e) => updateParagraph(pIndex, e.target.value)}
                                  rows={4}
                                />
                              </div>
                            ))}
                            <div className="flex justify-end gap-2">
                              <Button variant="outline" size="sm" onClick={cancelEdit}>
                                <X className="w-4 h-4 mr-1" />
                                Cancel
                              </Button>
                              <Button size="sm" onClick={saveEdit}>
                                <Save className="w-4 h-4 mr-1" />
                                Save
                              </Button>
                            </div>
                          </div>
                        ) : (
                          // View Mode
                          <div className="prose prose-sm max-w-none">
                            {finding.paragraphs.map((para, pIndex) => (
                              <p key={pIndex} className="text-foreground leading-relaxed">
                                {para}
                              </p>
                            ))}
                            {finding.key_points && finding.key_points.length > 0 && (
                              <div className="mt-4">
                                <strong>Key Points:</strong>
                                <ul className="list-disc pl-5 mt-2">
                                  {finding.key_points.map((point, kIndex) => (
                                    <li key={kIndex}>{point}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              ))}
            </div>

            {/* Add Finding Button */}
            <Button
              variant="outline"
              onClick={addFinding}
              disabled={isLoading || isGenerating}
              className="w-full border-dashed"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Finding
            </Button>

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
              <Button onClick={handleConfirm} disabled={isLoading || expandedFindings.length === 0} className="bg-success text-success-foreground hover:bg-success/90">
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Continue to Snapshot Table
                  </>
                )}
              </Button>
            </div>
          </>
        )}
      </CardContent>

      <AlertDialog open={pendingDeleteIndex !== null} onOpenChange={(open) => { if (!open) setPendingDeleteIndex(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete finding?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove this finding. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteFinding} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
