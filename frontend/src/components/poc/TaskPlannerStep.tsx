/**
 * Phase 2 – Task Planner (Engagement Planner) Step
 *
 * After the Word report is generated (Phase 1, Steps 1-7), this step
 * allows the advisor to configure engagement settings, preview the
 * generated task rows, and export the Excel (.xlsx) advisor task list.
 */
import React, { useState, useEffect } from 'react';
import {
  Loader2,
  AlertCircle,
  Download,
  Settings2,
  TableProperties,
  BarChart3,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// ---------- Types ----------

interface TaskRow {
  rec_number: number;
  recommendation: string;
  owner: string;
  task: string;
  advisorHrs: number;
  advisor: string | null;
  status: string;
  notes: string;
  timing: string;
}

interface TaskSummary {
  total_bba_hours: number;
  max_hours_per_month: number;
  monthly_hours: Record<string, number>;
  warnings: string[];
}

interface TaskPlannerSettings {
  lead_advisor: string;
  support_advisor: string;
  advisor_count: number;
  max_hours_per_month: number;
  start_month: number;
  start_year: number;
}

interface TaskPlannerStepProps {
  projectId: string;
  onBack: () => void;
  className?: string;
  onLoadingStateChange?: (isLoading: boolean) => void;
}

// ---------- Helpers ----------

const MONTHS = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' },
];

const currentYear = new Date().getFullYear();
const YEARS = Array.from({ length: 6 }, (_, i) => currentYear + i);

const STATUS_COLOURS: Record<string, string> = {
  'Not yet started': 'bg-gray-100 text-gray-700',
  'In progress': 'bg-yellow-100 text-yellow-800',
  'Complete': 'bg-green-100 text-green-800',
  'Awaiting review': 'bg-blue-100 text-blue-800',
};

// ---------- Component ----------

export function TaskPlannerStep({ projectId, onBack, className, onLoadingStateChange }: TaskPlannerStepProps) {
  // --- settings form state ---
  const [settings, setSettings] = useState<TaskPlannerSettings>({
    lead_advisor: '',
    support_advisor: '',
    advisor_count: 1,
    max_hours_per_month: 20,
    start_month: new Date().getMonth() + 1,
    start_year: currentYear,
  });

  // --- preview / export state ---
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [summary, setSummary] = useState<TaskSummary | null>(null);
  const [hasPreview, setHasPreview] = useState(false);

  // --- UI state ---
  const [isLoadingProject, setIsLoadingProject] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [showSummary, setShowSummary] = useState(true);
  const [activeSection, setActiveSection] = useState<'settings' | 'preview'>('settings');

  // Notify parent of loading state changes
  useEffect(() => {
    if (onLoadingStateChange) {
      onLoadingStateChange(isLoadingProject || isGenerating || isExporting);
    }
  }, [isLoadingProject, isGenerating, isExporting, onLoadingStateChange]);

  // --- Load existing settings/tasks from the project on mount ---
  useEffect(() => {
    loadExistingData();
  }, [projectId]);

  const getAuthHeaders = (): Record<string, string> => {
    const token = localStorage.getItem('auth_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const loadExistingData = async () => {
    setIsLoadingProject(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}`, {
        headers: { ...getAuthHeaders() },
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Failed to load project');

      const result = await response.json();
      const project = result.project;

      // Pre-fill settings if they were saved before
      if (project.task_planner_settings) {
        setSettings(project.task_planner_settings);
        setSettingsSaved(true);
      }

      // Pre-fill tasks/summary if already generated
      if (project.task_planner_tasks && project.task_planner_summary) {
        setTasks(project.task_planner_tasks);
        setSummary(project.task_planner_summary);
        setHasPreview(true);
        setActiveSection('preview');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load project data');
    } finally {
      setIsLoadingProject(false);
    }
  };

  // --- Save settings & generate preview ---
  const handleGeneratePreview = async () => {
    // Validation
    if (!settings.lead_advisor.trim()) {
      setError('Lead advisor name is required');
      return;
    }
    if (settings.advisor_count < 1) {
      setError('At least 1 advisor is required');
      return;
    }
    if (settings.max_hours_per_month < 1) {
      setError('Maximum hours per month must be at least 1');
      return;
    }

    setIsGenerating(true);
    setError(null);

    try {
      // Call the preview endpoint with settings (it saves settings + generates tasks)
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/tasks/preview`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        credentials: 'include',
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to generate preview' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();
      setTasks(result.tasks || []);
      setSummary(result.summary || null);
      setHasPreview(true);
      setSettingsSaved(true);
      setActiveSection('preview');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate preview');
    } finally {
      setIsGenerating(false);
    }
  };

  // --- Export to Excel ---
  const handleExportExcel = async () => {
    setIsExporting(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/tasks/export/excel`, {
        method: 'POST',
        headers: { ...getAuthHeaders() },
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to export' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      // Extract filename from Content-Disposition header or fallback
      const disposition = response.headers.get('Content-Disposition');
      let filename = 'Advisor_Task_List.xlsx';
      if (disposition) {
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match) filename = match[1];
      }

      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export Excel');
    } finally {
      setIsExporting(false);
    }
  };

  // --- Loading state ---
  if (isLoadingProject) {
    return (
      <Card className={cn('w-full', className)}>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <span className="ml-3 text-muted-foreground">Loading task planner...</span>
        </CardContent>
      </Card>
    );
  }

  // --- Render ---
  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <TableProperties className="w-5 h-5" />
                Phase 2 – Step 1: Excel Engagement Planner
              </CardTitle>
              <CardDescription>
                Configure advisor settings, preview tasks derived from the 12-month plan, and export to Excel.
              </CardDescription>
            </div>
            {hasPreview && (
              <Button onClick={handleExportExcel} disabled={isExporting}>
                {isExporting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Exporting...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 mr-2" />
                    Export to Excel (.xlsx)
                  </>
                )}
              </Button>
            )}
          </div>
        </CardHeader>
      </Card>

      {/* Error Display */}
      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span className="text-red-700">{error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">
            &times;
          </button>
        </div>
      )}

      {/* Section Tabs */}
      <div className="flex gap-2">
        <Button
          variant={activeSection === 'settings' ? 'default' : 'outline'}
          onClick={() => setActiveSection('settings')}
          className="gap-2"
        >
          <Settings2 className="w-4 h-4" />
          Engagement Settings
          {settingsSaved && <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />}
        </Button>
        <Button
          variant={activeSection === 'preview' ? 'default' : 'outline'}
          onClick={() => setActiveSection('preview')}
          disabled={!hasPreview}
          className="gap-2"
        >
          <TableProperties className="w-4 h-4" />
          Task Preview
          {hasPreview && <Badge variant="secondary" className="ml-1">{tasks.length}</Badge>}
        </Button>
      </div>

      {/* ─────────── SETTINGS SECTION ─────────── */}
      {activeSection === 'settings' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Settings2 className="w-5 h-5" />
              Engagement Settings
            </CardTitle>
            <CardDescription>
              Configure the advisors and engagement timeline. These settings determine how tasks
              and hours are allocated in the Excel planner.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Advisor Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="lead_advisor">Lead Advisor *</Label>
                <Input
                  id="lead_advisor"
                  placeholder="e.g. John Smith"
                  value={settings.lead_advisor}
                  onChange={(e) => setSettings((s) => ({ ...s, lead_advisor: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="support_advisor">Support Advisor</Label>
                <Input
                  id="support_advisor"
                  placeholder="e.g. Jane Doe (optional)"
                  value={settings.support_advisor}
                  onChange={(e) => setSettings((s) => ({ ...s, support_advisor: e.target.value }))}
                />
              </div>
            </div>

            {/* Capacity */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="advisor_count">Number of Advisors *</Label>
                <Input
                  id="advisor_count"
                  type="number"
                  min={1}
                  max={20}
                  value={settings.advisor_count}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, advisor_count: parseInt(e.target.value) || 1 }))
                  }
                />
                <p className="text-xs text-muted-foreground">
                  Total advisors working on this engagement
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="max_hours">Max Hours per Month *</Label>
                <Input
                  id="max_hours"
                  type="number"
                  min={1}
                  max={200}
                  value={settings.max_hours_per_month}
                  onChange={(e) =>
                    setSettings((s) => ({
                      ...s,
                      max_hours_per_month: parseInt(e.target.value) || 20,
                    }))
                  }
                />
                <p className="text-xs text-muted-foreground">
                  Combined capacity: {settings.advisor_count * settings.max_hours_per_month} hrs/month
                </p>
              </div>
            </div>

            {/* Timeline */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Start Month *</Label>
                <Select
                  value={String(settings.start_month)}
                  onValueChange={(val) =>
                    setSettings((s) => ({ ...s, start_month: parseInt(val) }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select month" />
                  </SelectTrigger>
                  <SelectContent>
                    {MONTHS.map((m) => (
                      <SelectItem key={m.value} value={String(m.value)}>
                        {m.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Start Year *</Label>
                <Select
                  value={String(settings.start_year)}
                  onValueChange={(val) =>
                    setSettings((s) => ({ ...s, start_year: parseInt(val) }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select year" />
                  </SelectTrigger>
                  <SelectContent>
                    {YEARS.map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Generate Button */}
            <div className="flex justify-end pt-4 border-t">
              <Button
                onClick={handleGeneratePreview}
                disabled={isGenerating}
                size="lg"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Generating Tasks...
                  </>
                ) : (
                  <>
                    Generate Task Preview
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ─────────── PREVIEW SECTION ─────────── */}
      {activeSection === 'preview' && hasPreview && (
        <>
          {/* Summary Card */}
          {summary && (
            <Card>
              <CardHeader
                className="cursor-pointer"
                onClick={() => setShowSummary(!showSummary)}
              >
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <BarChart3 className="w-5 h-5" />
                    Capacity Summary
                  </CardTitle>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline">
                      {summary.total_bba_hours.toFixed(1)} total BBA hours
                    </Badge>
                    {summary.warnings.length > 0 && (
                      <Badge variant="destructive" className="gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        {summary.warnings.length} warning{summary.warnings.length > 1 ? 's' : ''}
                      </Badge>
                    )}
                    {showSummary ? (
                      <ChevronUp className="w-4 h-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-muted-foreground" />
                    )}
                  </div>
                </div>
              </CardHeader>

              {showSummary && (
                <CardContent className="space-y-4">
                  {/* Monthly Hours Table */}
                  {Object.keys(summary.monthly_hours).length > 0 && (
                    <div className="border rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead className="bg-muted">
                          <tr>
                            <th className="p-3 text-left font-semibold">Month</th>
                            <th className="p-3 text-right font-semibold">BBA Hours</th>
                            <th className="p-3 text-right font-semibold">Capacity</th>
                            <th className="p-3 text-right font-semibold">Utilisation</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(summary.monthly_hours)
                            .sort(([a], [b]) => a.localeCompare(b))
                            .map(([month, hours]) => {
                              const capacity = summary.max_hours_per_month;
                              const utilisation = capacity > 0 ? (hours / capacity) * 100 : 0;
                              const isOver = hours > capacity;
                              return (
                                <tr
                                  key={month}
                                  className={cn('border-t', isOver && 'bg-red-50')}
                                >
                                  <td className="p-3 font-medium">{month}</td>
                                  <td className={cn('p-3 text-right', isOver && 'text-red-600 font-semibold')}>
                                    {hours.toFixed(1)}
                                  </td>
                                  <td className="p-3 text-right text-muted-foreground">
                                    {capacity.toFixed(1)}
                                  </td>
                                  <td className="p-3 text-right">
                                    <span
                                      className={cn(
                                        'inline-block px-2 py-0.5 rounded text-xs font-medium',
                                        utilisation > 100
                                          ? 'bg-red-100 text-red-700'
                                          : utilisation > 80
                                            ? 'bg-yellow-100 text-yellow-700'
                                            : 'bg-green-100 text-green-700'
                                      )}
                                    >
                                      {utilisation.toFixed(0)}%
                                    </span>
                                  </td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Warnings */}
                  {summary.warnings.length > 0 && (
                    <div className="space-y-2">
                      {summary.warnings.map((warning, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg"
                        >
                          <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                          <span className="text-sm text-amber-800">{warning}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          )}

          {/* Task Table */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <TableProperties className="w-5 h-5" />
                    Advisor Task List
                  </CardTitle>
                  <CardDescription>
                    {tasks.length} tasks generated from {new Set(tasks.map((t) => t.rec_number)).size} recommendations
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setActiveSection('settings')}
                  >
                    <Settings2 className="w-4 h-4 mr-2" />
                    Edit Settings
                  </Button>
                  <Button onClick={handleExportExcel} disabled={isExporting}>
                    {isExporting ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Exporting...
                      </>
                    ) : (
                      <>
                        <Download className="w-4 h-4 mr-2" />
                        Export to Excel
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="border rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#1a365d] text-white">
                    <tr>
                      <th className="p-3 text-left font-semibold whitespace-nowrap">Rec #</th>
                      <th className="p-3 text-left font-semibold">Recommendation</th>
                      <th className="p-3 text-left font-semibold">Owner</th>
                      <th className="p-3 text-left font-semibold min-w-[300px]">Task</th>
                      <th className="p-3 text-right font-semibold whitespace-nowrap">Advisor Hrs</th>
                      <th className="p-3 text-left font-semibold">Advisor</th>
                      <th className="p-3 text-left font-semibold">Status</th>
                      <th className="p-3 text-left font-semibold">Timing</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.map((task, idx) => (
                      <tr
                        key={idx}
                        className={cn(
                          'border-t',
                          idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'
                        )}
                      >
                        <td className="p-3 font-bold text-primary">{task.rec_number}</td>
                        <td className="p-3 max-w-[200px]">
                          <span className="line-clamp-2">{task.recommendation}</span>
                        </td>
                        <td className="p-3">
                          <Badge
                            variant={task.owner === 'BBA' ? 'default' : 'secondary'}
                            className="text-xs"
                          >
                            {task.owner}
                          </Badge>
                        </td>
                        <td className="p-3">
                          <span className="line-clamp-3">{task.task}</span>
                        </td>
                        <td className="p-3 text-right font-mono">
                          {task.advisorHrs > 0 ? task.advisorHrs.toFixed(1) : '—'}
                        </td>
                        <td className="p-3 text-muted-foreground">
                          {task.advisor || '—'}
                        </td>
                        <td className="p-3">
                          <span
                            className={cn(
                              'inline-block px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap',
                              STATUS_COLOURS[task.status] || 'bg-gray-100 text-gray-700'
                            )}
                          >
                            {task.status}
                          </span>
                        </td>
                        <td className="p-3 text-muted-foreground whitespace-nowrap">
                          {task.timing}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* Bottom Actions */}
      <div className="flex justify-between pt-2">
        <Button variant="outline" onClick={onBack}>
          Back to Report
        </Button>
        {hasPreview && (
          <Button onClick={handleExportExcel} disabled={isExporting} size="lg">
            {isExporting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Exporting...
              </>
            ) : (
              <>
                <Download className="w-4 h-4 mr-2" />
                Export to Excel (.xlsx)
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
