/**
 * Step 7: Review & Edit Component
 * Final review with export capability
 */
import React, { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle2, AlertCircle, FileText, Download, RefreshCw, Eye, Edit2, ArrowRight, TableProperties } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface BBAProject {
  id: string;
  client_name: string;
  industry: string;
  executive_summary?: string;
  draft_findings?: any;
  expanded_findings?: any;
  snapshot_table?: any;
  twelve_month_plan?: any;
  report_version?: number;
}

interface ReviewEditStepProps {
  projectId: string;
  onBack: () => void;
  onContinueToPhase2?: () => void;
  className?: string;
  onLoadingStateChange?: (isLoading: boolean) => void;
}

export function ReviewEditStep({ projectId, onBack, onContinueToPhase2, className, onLoadingStateChange }: ReviewEditStepProps) {
  const [project, setProject] = useState<BBAProject | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(false);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('summary');
  const [editingSummary, setEditingSummary] = useState(false);
  const [summaryDraft, setSummaryDraft] = useState('');
  const [hasTriedAutoGenerate, setHasTriedAutoGenerate] = useState(false);
  
  // Use ref to store the callback to avoid infinite loops
  const onLoadingStateChangeRef = useRef(onLoadingStateChange);
  useEffect(() => {
    onLoadingStateChangeRef.current = onLoadingStateChange;
  }, [onLoadingStateChange]);

  // Notify parent of loading state changes
  useEffect(() => {
    if (onLoadingStateChangeRef.current) {
      onLoadingStateChangeRef.current(isLoading || isExporting || isGeneratingSummary);
    }
  }, [isLoading, isExporting, isGeneratingSummary]);

  // Load project data
  useEffect(() => {
    loadProject();
  }, [projectId]);

  const loadProject = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to load project');
      }

      const result = await response.json();
      console.log('Project data loaded:', result.project);
      console.log('Snapshot table data:', result.project?.snapshot_table);
      setProject(result.project);
      setSummaryDraft(result.project.executive_summary || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load project');
    } finally {
      setIsLoading(false);
    }
  };

  // Generate executive summary
  const handleGenerateSummary = async () => {
    setIsGeneratingSummary(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/executive-summary/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to generate summary' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();
      setProject((prev) => prev ? { ...prev, executive_summary: result.executive_summary } : null);
      setSummaryDraft(result.executive_summary || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate summary');
    } finally {
      setIsGeneratingSummary(false);
    }
  };

  // Auto-generate summary when project loads and no summary exists
  useEffect(() => {
    if (project && !project.executive_summary && !hasTriedAutoGenerate) {
      setHasTriedAutoGenerate(true);
      handleGenerateSummary();
    }
  }, [project, hasTriedAutoGenerate]);

  // Export to Word
  const handleExport = async () => {
    setIsExporting(true);
    setExportError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/export/docx`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to export' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `BBA_Diagnostic_Report_${project?.client_name?.replace(/\s+/g, '_') || 'Client'}.docx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Failed to export');
    } finally {
      setIsExporting(false);
    }
  };

  // Save summary edits
  const saveSummary = async () => {
    // This would call an API to save the edited summary
    // For now, we just update locally
    setProject((prev) => prev ? { ...prev, executive_summary: summaryDraft } : null);
    setEditingSummary(false);
  };

  if (isLoading) {
    return (
      <Card className={cn('w-full', className)}>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </CardContent>
      </Card>
    );
  }

  if (error || !project) {
    return (
      <Card className={cn('w-full', className)}>
        <CardContent className="py-12">
          <div className="flex items-center justify-center gap-2 text-red-500">
            <AlertCircle className="w-5 h-5" />
            <span>{error || 'Project not found'}</span>
          </div>
          <div className="flex justify-center mt-4">
            <Button onClick={loadProject}>Retry</Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Step 7: Review & Export</CardTitle>
            <CardDescription>
              Review the complete report and export to Word document.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">Version {project.report_version || 1}</Badge>
            <Button onClick={handleExport} disabled={isExporting}>
              {isExporting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 mr-2" />
                  Export to Word
                </>
              )}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Export Error */}
        {exportError && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <span className="text-red-700">{exportError}</span>
          </div>
        )}

        {/* Client Info */}
        <div className="p-4 bg-muted rounded-lg">
          <h3 className="font-semibold text-lg">{project.client_name}</h3>
          <p className="text-muted-foreground">{project.industry}</p>
        </div>

        {/* Tabs for different sections */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="summary">Executive Summary</TabsTrigger>
            <TabsTrigger value="findings">Findings</TabsTrigger>
            <TabsTrigger value="snapshot">Snapshot</TabsTrigger>
            <TabsTrigger value="plan">12-Month Plan</TabsTrigger>
            <TabsTrigger value="preview">Preview</TabsTrigger>
          </TabsList>

          {/* Executive Summary Tab */}
          <TabsContent value="summary" className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold">Executive Summary</h4>
              <div className="flex gap-2">
                {project.executive_summary && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setEditingSummary(!editingSummary)}
                  >
                    {editingSummary ? (
                      <>
                        <Eye className="w-4 h-4 mr-2" />
                        Preview
                      </>
                    ) : (
                      <>
                        <Edit2 className="w-4 h-4 mr-2" />
                        Edit
                      </>
                    )}
                  </Button>
                )}
              </div>
            </div>

            {isGeneratingSummary && !project.executive_summary && (
              <p className="text-sm text-muted-foreground">
                Generating executive summary...
              </p>
            )}

            {editingSummary ? (
              <div className="space-y-2">
                <Textarea
                  value={summaryDraft}
                  onChange={(e) => setSummaryDraft(e.target.value)}
                  rows={10}
                  className="font-normal"
                />
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setEditingSummary(false)}>
                    Cancel
                  </Button>
                  <Button onClick={saveSummary}>Save Changes</Button>
                </div>
              </div>
            ) : (
              <div className="prose prose-sm max-w-none">
                {project.executive_summary ? (
                  <p className="whitespace-pre-wrap">{project.executive_summary}</p>
                ) : (
                  <p className="text-muted-foreground italic">
                    No executive summary generated yet. Click "Generate Summary" to create one.
                  </p>
                )}
              </div>
            )}
          </TabsContent>

          {/* Findings Tab */}
          <TabsContent value="findings" className="space-y-4">
            <h4 className="font-semibold">Key Findings - Ranked by Importance</h4>
            {project.expanded_findings?.expanded_findings ? (
              <div className="space-y-4">
                {project.expanded_findings.expanded_findings.map((finding: any, index: number) => (
                  <div key={index} className="border rounded-lg p-4">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-bold text-xl text-primary">{finding.rank}</span>
                      <h5 className="font-semibold">{finding.title}</h5>
                    </div>
                    <div className="prose prose-sm max-w-none">
                      {finding.paragraphs?.map((para: string, pIndex: number) => (
                        <p key={pIndex}>{para}</p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground italic">No expanded findings available.</p>
            )}
          </TabsContent>

          {/* Snapshot Tab */}
          <TabsContent value="snapshot" className="space-y-4">
            <h4 className="font-semibold">Key Findings & Recommendations Snapshot</h4>
            {(() => {
              // Try different possible data structures
              const snapshotData = project.snapshot_table?.snapshot_table || project.snapshot_table;
              const rows = snapshotData?.rows || [];
              
              if (rows.length > 0) {
                return (
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full">
                      <thead className="bg-muted">
                        <tr>
                          <th className="p-3 text-left font-semibold">#</th>
                          <th className="p-3 text-left font-semibold">Priority Area</th>
                          <th className="p-3 text-left font-semibold">Key Finding</th>
                          <th className="p-3 text-left font-semibold">Recommendation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((row: any, index: number) => (
                          <tr key={index} className="border-t">
                            <td className="p-3 font-bold">{row.rank}</td>
                            <td className="p-3">{row.priority_area}</td>
                            <td className="p-3">{row.key_finding}</td>
                            <td className="p-3">{row.recommendation}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                );
              }
              return <p className="text-muted-foreground italic">No snapshot table available.</p>;
            })()}
          </TabsContent>

          {/* Plan Tab */}
          <TabsContent value="plan" className="space-y-4">
            <h4 className="font-semibold">12-Month Recommendations Plan</h4>
            {project.twelve_month_plan?.recommendations ? (
              <div className="space-y-4">
                {project.twelve_month_plan.plan_notes && (
                  <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm text-blue-800">{project.twelve_month_plan.plan_notes}</p>
                  </div>
                )}
                {project.twelve_month_plan.recommendations.map((rec: any, index: number) => (
                  <div key={index} className="border rounded-lg p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <span className="font-bold text-xl text-primary">{rec.number}</span>
                      <div>
                        <h5 className="font-semibold">{rec.title}</h5>
                        <Badge variant="outline">{rec.timing}</Badge>
                      </div>
                    </div>
                    <div className="space-y-3 text-sm">
                      <div>
                        <strong>Purpose:</strong>
                        <p className="text-muted-foreground">{rec.purpose}</p>
                      </div>
                      <div>
                        <strong>Key Objectives:</strong>
                        <ul className="list-disc pl-5 text-muted-foreground">
                          {rec.key_objectives?.map((obj: string, i: number) => (
                            <li key={i}>{obj}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground italic">No 12-month plan available.</p>
            )}
          </TabsContent>

          {/* Preview Tab */}
          <TabsContent value="preview" className="space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <FileText className="w-5 h-5" />
              <h4 className="font-semibold">Document Preview</h4>
            </div>
            <div className="border rounded-lg p-8 bg-white min-h-[600px] prose prose-sm max-w-none">
              {/* Title Page */}
              <div className="text-center mb-12">
                <h1 className="text-2xl font-bold mb-4">Diagnostic Findings & Recommendations Report</h1>
                <h2 className="text-xl">{project.client_name}</h2>
                <p className="text-muted-foreground">{new Date().toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })}</p>
              </div>

              {/* Executive Summary */}
              {project.executive_summary && (
                <div className="mb-8">
                  <h2 className="text-lg font-bold border-b pb-2 mb-4">Executive Summary</h2>
                  <p className="whitespace-pre-wrap">{project.executive_summary}</p>
                </div>
              )}

              {/* Key Findings Preview */}
              {project.expanded_findings?.expanded_findings && (
                <div className="mb-8">
                  <h2 className="text-lg font-bold border-b pb-2 mb-4">Key Findings - Ranked by Importance</h2>
                  <p className="text-sm text-muted-foreground">
                    {project.expanded_findings.expanded_findings.length} findings detailed
                  </p>
                </div>
              )}

              {/* 12-Month Plan Preview */}
              {project.twelve_month_plan?.recommendations && (
                <div className="mb-8">
                  <h2 className="text-lg font-bold border-b pb-2 mb-4">12-Month Recommendations Plan</h2>
                  <p className="text-sm text-muted-foreground">
                    {project.twelve_month_plan.recommendations.length} recommendations outlined
                  </p>
                </div>
              )}

              <div className="text-center text-xs text-muted-foreground mt-12 pt-4 border-t">
                Confidential - Prepared by Benchmark Business Advisory for {project.client_name}
              </div>
            </div>
          </TabsContent>
        </Tabs>

        {/* Action Buttons */}
        <div className="flex justify-between pt-4 border-t">
          <Button variant="outline" onClick={onBack}>
            Back
          </Button>
          <div className="flex gap-2">
            {onContinueToPhase2 && (
              <Button onClick={onContinueToPhase2} className="gap-2">
                Phase 2: Task Planner
                <ArrowRight className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
