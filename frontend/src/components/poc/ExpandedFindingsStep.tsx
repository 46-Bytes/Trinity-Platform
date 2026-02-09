/**
 * Step 4: Expanded Findings Component
 * Displays expanded findings with full paragraphs for each finding
 */
import React, { useState } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Pencil, Save, X, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
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
}

export function ExpandedFindingsStep({ projectId, onComplete, onBack, className }: ExpandedFindingsStepProps) {
  const [expandedFindings, setExpandedFindings] = useState<ExpandedFinding[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<ExpandedFinding | null>(null);
  const [tokensUsed, setTokensUsed] = useState(0);
  const [openItems, setOpenItems] = useState<number[]>([]);

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
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();
      const findingsData = result.expanded_findings?.expanded_findings || result.expanded_findings || [];
      setExpandedFindings(findingsData);
      setTokensUsed(result.tokens_used || 0);
      // Open all items by default
      setOpenItems(findingsData.map((_: any, i: number) => i));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to expand findings');
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

  // Save edit
  const saveEdit = () => {
    if (editingIndex !== null && editForm) {
      const updated = [...expandedFindings];
      updated[editingIndex] = editForm;
      setExpandedFindings(updated);
      setEditingIndex(null);
      setEditForm(null);
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

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader>
        <CardTitle>Step 4: Expanded Findings</CardTitle>
        <CardDescription>
          Review the detailed explanations for each finding. Edit as needed before continuing.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Generate Button */}
        {expandedFindings.length === 0 && !isGenerating && (
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
        {expandedFindings.length > 0 && (
          <>
            {/* Token Usage */}
            {tokensUsed > 0 && (
              <p className="text-sm text-muted-foreground">
                Tokens used: {tokensUsed.toLocaleString()}
              </p>
            )}

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
              <Button onClick={handleConfirm} disabled={isLoading || expandedFindings.length === 0}>
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
    </Card>
  );
}
