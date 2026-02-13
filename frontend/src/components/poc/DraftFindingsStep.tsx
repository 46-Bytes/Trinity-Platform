/**
 * Step 3: Draft Findings Component
 * Displays AI-generated findings for advisor review and editing
 */
import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, AlertCircle, GripVertical, Pencil, Save, X, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface Finding {
  rank: number;
  title: string;
  summary: string;
  priority_area: string;
  impact: 'high' | 'medium' | 'low';
  urgency: 'immediate' | 'short-term' | 'medium-term';
}

interface DraftFindingsStepProps {
  projectId: string;
  onComplete: (findings: Finding[]) => void;
  onBack: () => void;
  className?: string;
  onLoadingStateChange?: (isLoading: boolean) => void;
}

export function DraftFindingsStep({ projectId, onComplete, onBack, className, onLoadingStateChange }: DraftFindingsStepProps) {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Finding | null>(null);
  const [tokensUsed, setTokensUsed] = useState(0);
  const [analysisNotes, setAnalysisNotes] = useState<string>('');

  // Load existing findings on mount
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
          
          console.log('Loading draft findings from project:', project?.draft_findings);
          
          if (project?.draft_findings) {
            const findingsData = project.draft_findings.findings || 
                                 (Array.isArray(project.draft_findings) ? project.draft_findings : []);
            console.log('Extracted findings data:', findingsData);
            if (findingsData && findingsData.length > 0) {
              setFindings(findingsData);
              setAnalysisNotes(project.draft_findings?.analysis_notes || '');
              console.log('Successfully loaded', findingsData.length, 'findings');
            } else {
              console.log('No findings found in draft_findings');
            }
          } else {
            console.log('No draft_findings in project');
          }
        }
      } catch (err) {
        console.error('Failed to load existing findings:', err);
      } finally {
        setIsInitialLoading(false);
      }
    };

    if (projectId) {
      loadExistingData();
    }
  }, [projectId]);

  useEffect(() => {
    if (onLoadingStateChange) {
      onLoadingStateChange(isLoading || isGenerating);
    }
  }, [isLoading, isGenerating, onLoadingStateChange]);

  // Generate draft findings
  const handleGenerate = async (customInstructions?: string) => {
    setIsGenerating(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step3/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify({
          custom_instructions: customInstructions || null,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to generate findings' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();
      const findingsData = result.findings?.findings || result.findings || [];
      setFindings(findingsData);
      setTokensUsed(result.tokens_used || 0);
      setAnalysisNotes(result.findings?.analysis_notes || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate findings');
    } finally {
      setIsGenerating(false);
    }
  };

  // Confirm findings and proceed
  const handleConfirm = async () => {
    if (findings.length === 0) {
      setError('No findings to confirm. Please generate findings first.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step3/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify({
          findings: findings,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to confirm findings' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      // Success - proceed to next step
      setIsLoading(false);
      
      // Call onComplete to proceed to next step
      setTimeout(() => {
        onComplete(findings);
      }, 50);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to confirm findings';
      setError(errorMessage);
      console.error('Error confirming findings:', err);
      setIsLoading(false);
    }
  };

  // Start editing a finding
  const startEdit = (index: number) => {
    setEditingIndex(index);
    setEditForm({ ...findings[index] });
  };

  // Save edited finding
  const saveEdit = () => {
    if (editingIndex !== null && editForm) {
      const updated = [...findings];
      updated[editingIndex] = editForm;
      setFindings(updated);
      setEditingIndex(null);
      setEditForm(null);
    }
  };

  // Cancel editing
  const cancelEdit = () => {
    setEditingIndex(null);
    setEditForm(null);
  };

  // Move finding up/down
  const moveFinding = (index: number, direction: 'up' | 'down') => {
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= findings.length) return;

    const updated = [...findings];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    // Update ranks
    updated.forEach((f, i) => (f.rank = i + 1));
    setFindings(updated);
  };

  // Delete finding
  const deleteFinding = (index: number) => {
    const updated = findings.filter((_, i) => i !== index);
    updated.forEach((f, i) => (f.rank = i + 1));
    setFindings(updated);
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'high':
        return 'bg-red-100 text-red-800 hover:bg-red-50 hover:text-red-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 hover:bg-yellow-50 hover:text-yellow-800';
      case 'low':
        return 'bg-green-100 text-green-800 hover:bg-green-50 hover:text-green-800';
      default:
        return 'bg-gray-100 text-gray-800 hover:bg-gray-50 hover:text-gray-800';
    }
  };

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'immediate':
        return 'bg-red-100 text-red-800 hover:bg-red-50 hover:text-red-800';
      case 'short-term':
        return 'bg-orange-100 text-orange-800 hover:bg-orange-50 hover:text-orange-800';
      case 'medium-term':
        return 'bg-blue-100 text-blue-800 hover:bg-blue-50 hover:text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800 hover:bg-gray-50 hover:text-gray-800';
    }
  };

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader>
        <CardTitle>Step 3: Draft Findings</CardTitle>
        <CardDescription>
          Review and edit the AI-generated findings. You can reorder, edit, or regenerate.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Initial Loading State */}
        {isInitialLoading && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground">Loading existing findings...</p>
          </div>
        )}

        {/* Generate Button */}
        {!isInitialLoading && findings.length === 0 && !isGenerating && (
          <div className="text-center py-8">
            <p className="text-muted-foreground mb-4">
              Click the button below to analyse your uploaded files and generate draft findings.
            </p>
            <Button onClick={() => handleGenerate()} size="lg">
              <RefreshCw className="w-4 h-4 mr-2" />
              Generate Draft Findings
            </Button>
          </div>
        )}

        {/* Loading State */}
        {isGenerating && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground">Analysing files and generating findings...</p>
            <p className="text-sm text-muted-foreground mt-2">This may take a minute or two.</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <span className="text-red-700">{error}</span>
            <Button variant="outline" size="sm" onClick={() => handleGenerate()} className="ml-auto">
              Retry
            </Button>
          </div>
        )}

        {/* Findings List */}
        {!isInitialLoading && findings.length > 0 && (
          <>
            {/* Analysis Notes */}
            {analysisNotes && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>Analysis Notes:</strong> {analysisNotes}
                </p>
              </div>
            )}

            {/* Token Usage */}
            {tokensUsed > 0 && (
              <p className="text-sm text-muted-foreground">
                Tokens used: {tokensUsed.toLocaleString()}
              </p>
            )}

            {/* Findings */}
            <div className="space-y-4">
              {findings.map((finding, index) => (
                <div
                  key={index}
                  className="border rounded-lg p-4 bg-card hover:shadow-sm transition-shadow"
                >
                  {editingIndex === index && editForm ? (
                    // Edit Mode
                    <div className="space-y-4">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-lg">#{finding.rank}</span>
                        <Input
                          value={editForm.title}
                          onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                          placeholder="Finding title"
                          className="flex-1"
                        />
                      </div>
                      <Textarea
                        value={editForm.summary}
                        onChange={(e) => setEditForm({ ...editForm, summary: e.target.value })}
                        placeholder="Finding summary"
                        rows={3}
                      />
                      <div className="flex gap-4">
                        <div className="flex-1">
                          <label className="text-sm font-medium">Priority Area</label>
                          <Input
                            value={editForm.priority_area}
                            onChange={(e) => setEditForm({ ...editForm, priority_area: e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Impact</label>
                          <select
                            value={editForm.impact}
                            onChange={(e) => setEditForm({ ...editForm, impact: e.target.value as any })}
                            className="w-full h-10 rounded-md border px-3"
                          >
                            <option value="high">High</option>
                            <option value="medium">Medium</option>
                            <option value="low">Low</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-sm font-medium">Urgency</label>
                          <select
                            value={editForm.urgency}
                            onChange={(e) => setEditForm({ ...editForm, urgency: e.target.value as any })}
                            className="w-full h-10 rounded-md border px-3"
                          >
                            <option value="immediate">Immediate</option>
                            <option value="short-term">Short-term</option>
                            <option value="medium-term">Medium-term</option>
                          </select>
                        </div>
                      </div>
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
                    <div className="flex gap-4">
                      {/* Drag Handle & Rank */}
                      <div className="flex flex-col items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => moveFinding(index, 'up')}
                          disabled={index === 0}
                        >
                          <GripVertical className="w-4 h-4 rotate-90" />
                        </Button>
                        <span className="font-bold text-2xl text-primary">{finding.rank}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => moveFinding(index, 'down')}
                          disabled={index === findings.length - 1}
                        >
                          <GripVertical className="w-4 h-4 rotate-90" />
                        </Button>
                      </div>

                      {/* Content */}
                      <div className="flex-1">
                        <div className="flex items-start justify-between">
                          <h4 className="font-semibold text-lg">{finding.title}</h4>
                          <div className="flex gap-2">
                            <Badge className={getImpactColor(finding.impact)}>
                              {finding.impact}
                            </Badge>
                            <Badge className={getUrgencyColor(finding.urgency)}>
                              {finding.urgency}
                            </Badge>
                          </div>
                        </div>
                        <p className="text-muted-foreground mt-1">{finding.summary}</p>
                        <p className="text-sm text-muted-foreground mt-2">
                          <strong>Priority Area:</strong> {finding.priority_area}
                        </p>
                      </div>

                      {/* Actions */}
                      <div className="flex flex-col gap-1">
                        <Button variant="ghost" size="sm" onClick={() => startEdit(index)}>
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteFinding(index)}
                          className="text-red-500 hover:text-red-700"
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Action Buttons */}
            <div className="flex justify-between pt-4 border-t">
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  onClick={onBack}
                  disabled={isLoading || isGenerating}
                >
                  Back
                </Button>
                <Button 
                  variant="outline" 
                  onClick={() => handleGenerate()}
                  disabled={isLoading || isGenerating}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Regenerate
                </Button>
              </div>
              <Button 
                onClick={handleConfirm} 
                disabled={isLoading || isGenerating || findings.length === 0}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Confirming...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Confirm & Continue to Expand Findings
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
