/**
 * Follow-up tools tab for an engagement.
 * Always shows BBA Builder and Strategy Workbook tools.
 * If a completed diagnostic exists, it can optionally be used as context.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch } from '@/store/hooks';
import { clearWorkbook } from '@/store/slices/strategyWorkbookReducer';
import { clearPlan } from '@/store/slices/strategicBusinessPlanReducer';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { BookOpen, FileText, Loader2, Wrench, ClipboardList } from 'lucide-react';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function normalizeUUID(uuid: string | null | undefined): string | null {
  if (!uuid) return null;
  const str = String(uuid).trim().toLowerCase();
  return str.replace(/^["'{]|["'}]$/g, '');
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  try {
    const d = new Date(value);
    return isNaN(d.getTime()) ? '—' : d.toLocaleDateString(undefined, { dateStyle: 'medium' });
  } catch {
    return '—';
  }
}

export interface FollowUpToolsTabProps {
  engagementId: string;
  diagnostics: Array<{
    id: string;
    status?: string;
    completed_at?: string | null;
    created_by_user_id?: string | null;
    completed_by_user_id?: string | null;
    tag?: string | null;
    [key: string]: unknown;
  }>;
  diagnosticTags?: Record<string, string>;
  currentUserId?: string | null;
  isAdmin?: boolean;
}

export function FollowUpToolsTab({
  engagementId,
  diagnostics,
  diagnosticTags = {},
  currentUserId,
  isAdmin = false,
}: FollowUpToolsTabProps) {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const [bbaLoading, setBbaLoading] = useState(false);
  const [swLoading, setSwLoading] = useState(false);
  const [sbpLoading, setSbpLoading] = useState(false);
  const [showBbaDialog, setShowBbaDialog] = useState(false);
  const [existingBbaStep, setExistingBbaStep] = useState<number>(0);
  const [existingBbaProjectId, setExistingBbaProjectId] = useState<string | null>(null);

  const completedDiagnostics = diagnostics.filter(
    (d) => (d.status || (d as any).status) === 'completed'
  );

  const canSeeDiagnostic = (d: (typeof completedDiagnostics)[0]) => {
    if (!isAdmin) return true;
    if (!currentUserId) return false;
    const createdBy = normalizeUUID(d.created_by_user_id ?? (d as any).createdByUserId);
    const completedBy = normalizeUUID(d.completed_by_user_id ?? (d as any).completedByUserId);
    const uid = normalizeUUID(currentUserId);
    return (createdBy && createdBy === uid) || (completedBy && completedBy === uid);
  };

  const visibleDiagnostics = completedDiagnostics.filter(canSeeDiagnostic);

  // Auto-use the most recent completed diagnostic as context (if any)
  const effectiveDiagnosticId = visibleDiagnostics.length > 0 ? visibleDiagnostics[0].id : null;

  const anyLoading = bbaLoading || swLoading || sbpLoading;

  const getAuthToken = () => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      toast.error('Not authenticated');
      return null;
    }
    return token;
  };

  const launchBba = async (forceNew: boolean = false) => {
    setBbaLoading(true);
    try {
      const token = getAuthToken();
      if (!token) return;

      let url: string;
      if (effectiveDiagnosticId) {
        url = `${API_BASE_URL}/api/poc/create-from-diagnostic?diagnostic_id=${effectiveDiagnosticId}${forceNew ? '&force_new=true' : ''}`;
      } else {
        url = `${API_BASE_URL}/api/poc/create-project?engagement_id=${engagementId}`;
      }

      const res = await fetch(url, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Failed to create BBA project' }));
        toast.error(err.detail || 'Failed to start BBA Builder');
        return;
      }
      const data = await res.json();
      const projectId = data.project_id;
      if (projectId) {
        navigate(`/dashboard/engagements/${engagementId}/bba`, { state: { bbaProjectId: projectId } });
      } else {
        toast.error('Invalid response from server');
      }
    } catch (e) {
      console.error(e);
      toast.error('Failed to start BBA Builder');
    } finally {
      setBbaLoading(false);
    }
  };

  const runBbaBuilder = async () => {
    const token = getAuthToken();
    if (!token) return;

    setBbaLoading(true);
    // Check for existing progressed BBA before creating/navigating
    try {
      const listRes = await fetch(`${API_BASE_URL}/api/poc?engagement_id=${engagementId}`, {
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (listRes.ok) {
        const listData = await listRes.json();
        const projects = listData.projects || [];
        const progressed = projects.find(
          (p: { max_step_reached?: number }) => (p.max_step_reached || 0) >= 2
        );
        if (progressed) {
          // Show confirmation dialog — user has work in progress
          setExistingBbaStep(progressed.max_step_reached || 0);
          setExistingBbaProjectId(progressed.id);
          setShowBbaDialog(true);
          setBbaLoading(false);
          return;
        }
      }
    } catch {
      // If pre-check fails, fall through to normal flow
    }

    await launchBba();
  };

  const runStrategyWorkbook = async () => {
    setSwLoading(true);
    try {
      const token = getAuthToken();
      if (!token) return;

      let url: string;
      if (effectiveDiagnosticId) {
        url = `${API_BASE_URL}/api/strategy-workbook/create-from-diagnostic?diagnostic_id=${effectiveDiagnosticId}`;
      } else {
        url = `${API_BASE_URL}/api/strategy-workbook/create-project?engagement_id=${engagementId}`;
      }

      const res = await fetch(url, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Failed to create strategy workbook' }));
        toast.error(err.detail || 'Failed to start Strategy Workbook');
        return;
      }
      const data = await res.json();
      const workbookId = data.workbook_id;
      if (workbookId) {
        dispatch(clearWorkbook());
        navigate(`/dashboard/engagements/${engagementId}/strategy-workbook`, { state: { workbookId } });
      } else {
        toast.error('Invalid response from server');
      }
    } catch (e) {
      console.error(e);
      toast.error('Failed to start Strategy Workbook');
    } finally {
      setSwLoading(false);
    }
  };

  const runStrategicBusinessPlan = async () => {
    setSbpLoading(true);
    try {
      const token = getAuthToken();
      if (!token) return;

      // Check for an existing plan for this engagement first
      try {
        const listRes = await fetch(`${API_BASE_URL}/api/strategic-business-plan/?engagement_id=${engagementId}`, {
          headers: { Authorization: `Bearer ${token}` },
          credentials: 'include',
        });
        if (listRes.ok) {
          const plans: Array<{ id: string; max_step_reached?: number; updated_at?: string }> = await listRes.json();
          if (plans.length > 0) {
            // Load the most recent plan (already sorted by updated_at desc from backend)
            const existing = plans[0];
            dispatch(clearPlan());
            navigate(`/dashboard/engagements/${engagementId}/strategic-business-plan`, { state: { sbpPlanId: existing.id } });
            return;
          }
        }
      } catch {
        // If pre-check fails, fall through to create
      }

      let url: string;
      if (effectiveDiagnosticId) {
        url = `${API_BASE_URL}/api/strategic-business-plan/create-from-diagnostic?diagnostic_id=${effectiveDiagnosticId}`;
      } else {
        url = `${API_BASE_URL}/api/strategic-business-plan/create?engagement_id=${engagementId}`;
      }

      const res = await fetch(url, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Failed to create strategic business plan' }));
        toast.error(err.detail || 'Failed to start Strategic Business Plan');
        return;
      }
      const data = await res.json();
      const planId = data.plan_id;
      if (planId) {
        dispatch(clearPlan());
        navigate(`/dashboard/engagements/${engagementId}/strategic-business-plan`, { state: { sbpPlanId: planId } });
      } else {
        toast.error('Invalid response from server');
      }
    } catch (e) {
      console.error(e);
      toast.error('Failed to start Strategic Business Plan');
    } finally {
      setSbpLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Wrench className="h-5 w-5 text-muted-foreground" />
          AI Tools
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Run AI-powered tools for this engagement.
          {effectiveDiagnosticId && ' A completed diagnostic will be used as context.'}
        </p>
      </div>

      {/* Tool cards - always visible and always enabled */}
      <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
        <Card className="flex flex-col">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Recommendations Report Builder
            </CardTitle>
            <CardDescription>
              Generate a Business Benchmark Analysis{effectiveDiagnosticId ? ' from your diagnostic data' : ' for this engagement'}.
            </CardDescription>
          </CardHeader>
          <CardContent className="mt-auto pt-4">
            <Button
              variant="outline"
              className="w-full sm:w-auto"
              disabled={anyLoading}
              onClick={runBbaBuilder}
            >
              {bbaLoading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <FileText className="h-4 w-4 mr-2" />
              )}
              Run Recommendations Report Builder
            </Button>
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              Strategy Workbook Creator
            </CardTitle>
            <CardDescription>
              Create a strategic planning workbook{effectiveDiagnosticId ? ' based on your diagnostic insights' : ' for this engagement'}.
            </CardDescription>
          </CardHeader>
          <CardContent className="mt-auto pt-4">
            <Button
              variant="outline"
              className="w-full sm:w-auto"
              disabled={anyLoading}
              onClick={runStrategyWorkbook}
            >
              {swLoading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <BookOpen className="h-4 w-4 mr-2" />
              )}
              Run Strategy Workbook
            </Button>
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <ClipboardList className="h-4 w-4" />
              Strategic Business Plan
            </CardTitle>
            <CardDescription>
              Build a professional Strategic Business Plan{effectiveDiagnosticId ? ' from your diagnostic and strategy workbook' : ' for this engagement'}.
            </CardDescription>
          </CardHeader>
          <CardContent className="mt-auto pt-4">
            <Button
              variant="outline"
              className="w-full sm:w-auto"
              disabled={anyLoading}
              onClick={runStrategicBusinessPlan}
            >
              {sbpLoading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <ClipboardList className="h-4 w-4 mr-2" />
              )}
              Run Strategic Business Plan
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Confirmation dialog when a progressed BBA already exists */}
      <AlertDialog open={showBbaDialog} onOpenChange={setShowBbaDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Existing Report In Progress</AlertDialogTitle>
            <AlertDialogDescription>
              You have an existing BBA report in progress (Step {existingBbaStep} of 9).
              Would you like to continue where you left off, or start fresh?
            </AlertDialogDescription>
            <p className="text-sm text-destructive mt-2 font-medium">
              Starting fresh will permanently delete all existing report data including uploaded files, findings, and plans.
            </p>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setShowBbaDialog(false);
                if (existingBbaProjectId) {
                  navigate(`/dashboard/engagements/${engagementId}/bba`, {
                    state: { bbaProjectId: existingBbaProjectId },
                  });
                } else {
                  launchBba();
                }
              }}
            >
              Continue Existing
            </AlertDialogAction>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                setShowBbaDialog(false);
                launchBba(true);
              }}
            >
              Start Fresh
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
