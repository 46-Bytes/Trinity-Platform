/**
 * Shared "run this tool" launch logic for BBA / Strategy Workbook / Strategic
 * Business Plan: check for an existing in-progress project for the
 * engagement, surface a "Continue vs Start Fresh" confirmation when found,
 * otherwise create (optionally from the most recent completed diagnostic)
 * and navigate to the tool's dedicated route.
 *
 * Extracted from FollowUpToolsTab.tsx so ModuleCard.tsx (Program Guide) can
 * reuse the exact same behavior instead of re-implementing it.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch } from '@/store/hooks';
import { clearWorkbook } from '@/store/slices/strategyWorkbookReducer';
import { clearPlan } from '@/store/slices/strategicBusinessPlanReducer';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export type ToolKey = 'bba' | 'strategy_workbook' | 'strategic_business_plan';

export interface ToolDialogState {
  open: boolean;
  title: string;
  description: string;
  warning: string;
}

export interface ToolLauncherState {
  loading: boolean;
  run: () => Promise<void>;
  dialog: ToolDialogState;
  continueExisting: () => void;
  startFresh: () => void;
  cancelDialog: () => void;
}

export interface UseToolLaunchersResult {
  effectiveDiagnosticId: string | null;
  anyLoading: boolean;
  tools: Record<ToolKey, ToolLauncherState>;
}

export interface DiagnosticSummary {
  id: string;
  status?: string;
  created_by_user_id?: string | null;
  completed_by_user_id?: string | null;
  [key: string]: unknown;
}

function getAuthToken(): string | null {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    toast.error('Not authenticated');
    return null;
  }
  return token;
}

export function useToolLaunchers(
  engagementId: string,
  diagnostics: DiagnosticSummary[],
  currentUserId?: string | null,
  isAdmin: boolean = false
): UseToolLaunchersResult {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();

  const [bbaLoading, setBbaLoading] = useState(false);
  const [swLoading, setSwLoading] = useState(false);
  const [sbpLoading, setSbpLoading] = useState(false);

  const [showBbaDialog, setShowBbaDialog] = useState(false);
  const [existingBbaStep, setExistingBbaStep] = useState<number>(0);
  const [existingBbaProjectId, setExistingBbaProjectId] = useState<string | null>(null);

  const [showSwDialog, setShowSwDialog] = useState(false);
  const [existingSwWorkbookId, setExistingSwWorkbookId] = useState<string | null>(null);
  const [existingSwStatus, setExistingSwStatus] = useState<string>('');

  const [showSbpDialog, setShowSbpDialog] = useState(false);
  const [existingSbpPlanId, setExistingSbpPlanId] = useState<string | null>(null);
  const [existingSbpStatus, setExistingSbpStatus] = useState<string>('');

  const completedDiagnostics = diagnostics.filter((d) => d.status === 'completed');

  const canSeeDiagnostic = (d: DiagnosticSummary) => {
    if (!isAdmin) return true;
    if (!currentUserId) return false;
    const normalize = (v: string | null | undefined) =>
      v ? String(v).trim().toLowerCase().replace(/^["'{]|["'}]$/g, '') : null;
    const createdBy = normalize((d.created_by_user_id as string) ?? (d.createdByUserId as string));
    const completedBy = normalize((d.completed_by_user_id as string) ?? (d.completedByUserId as string));
    const uid = normalize(currentUserId);
    return (createdBy && createdBy === uid) || (completedBy && completedBy === uid);
  };

  const visibleDiagnostics = completedDiagnostics.filter(canSeeDiagnostic);
  const effectiveDiagnosticId = visibleDiagnostics.length > 0 ? visibleDiagnostics[0].id : null;

  const anyLoading = bbaLoading || swLoading || sbpLoading;

  // ---- BBA ----
  const launchBba = async (forceNew: boolean = false) => {
    setBbaLoading(true);
    try {
      const token = getAuthToken();
      if (!token) return;

      const url = effectiveDiagnosticId
        ? `${API_BASE_URL}/api/poc/create-from-diagnostic?diagnostic_id=${effectiveDiagnosticId}${forceNew ? '&force_new=true' : ''}`
        : `${API_BASE_URL}/api/poc/create-project?engagement_id=${engagementId}`;

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

  const runBba = async () => {
    const token = getAuthToken();
    if (!token) return;

    setBbaLoading(true);
    try {
      const listRes = await fetch(`${API_BASE_URL}/api/poc?engagement_id=${engagementId}`, {
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (listRes.ok) {
        const listData = await listRes.json();
        const projects = listData.projects || [];
        const progressed = projects.find((p: { max_step_reached?: number }) => (p.max_step_reached || 0) >= 2);
        if (progressed) {
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

  // ---- Strategy Workbook ----
  const launchSwWorkbook = async (forceNew: boolean = false) => {
    setSwLoading(true);
    try {
      const token = getAuthToken();
      if (!token) return;

      const url = effectiveDiagnosticId
        ? `${API_BASE_URL}/api/strategy-workbook/create-from-diagnostic?diagnostic_id=${effectiveDiagnosticId}${forceNew ? '&force_new=true' : ''}`
        : `${API_BASE_URL}/api/strategy-workbook/create-project?engagement_id=${engagementId}`;

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

  const runStrategyWorkbook = async () => {
    const token = getAuthToken();
    if (!token) return;

    setSwLoading(true);
    try {
      const listRes = await fetch(`${API_BASE_URL}/api/strategy-workbook/?engagement_id=${engagementId}`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (listRes.ok) {
        const listData = await listRes.json();
        const workbooks: Array<{ id: string; status: string }> = listData.workbooks || [];
        const existing = workbooks[0];
        if (existing) {
          setExistingSwStatus(existing.status);
          setExistingSwWorkbookId(existing.id);
          setShowSwDialog(true);
          setSwLoading(false);
          return;
        }
      }
    } catch {
      // If pre-check fails, fall through to normal creation
    }

    await launchSwWorkbook();
  };

  // ---- Strategic Business Plan ----
  const launchSbp = async (forceNew: boolean = false) => {
    setSbpLoading(true);
    try {
      const token = getAuthToken();
      if (!token) return;

      const url = effectiveDiagnosticId
        ? `${API_BASE_URL}/api/strategic-business-plan/create-from-diagnostic?diagnostic_id=${effectiveDiagnosticId}${forceNew ? '&force_new=true' : ''}`
        : `${API_BASE_URL}/api/strategic-business-plan/create?engagement_id=${engagementId}${forceNew ? '&force_new=true' : ''}`;

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

  const runSbp = async () => {
    const token = getAuthToken();
    if (!token) return;

    setSbpLoading(true);
    try {
      const listRes = await fetch(`${API_BASE_URL}/api/strategic-business-plan/?engagement_id=${engagementId}`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (listRes.ok) {
        const plans: Array<{ id: string; status?: string; updated_at?: string }> = await listRes.json();
        if (plans.length > 0) {
          const existing = plans[0];
          setExistingSbpStatus(existing.status || 'in_progress');
          setExistingSbpPlanId(existing.id);
          setShowSbpDialog(true);
          setSbpLoading(false);
          return;
        }
      }
    } catch {
      // If pre-check fails, fall through to normal creation
    }

    await launchSbp();
  };

  return {
    effectiveDiagnosticId,
    anyLoading,
    tools: {
      bba: {
        loading: bbaLoading,
        run: runBba,
        dialog: {
          open: showBbaDialog,
          title: 'Existing Report In Progress',
          description: `You have an existing BBA report in progress (Step ${existingBbaStep} of 9). Would you like to continue where you left off, or start fresh?`,
          warning: 'Starting fresh will permanently delete all existing report data including uploaded files, findings, and plans.',
        },
        continueExisting: () => {
          setShowBbaDialog(false);
          if (existingBbaProjectId) {
            navigate(`/dashboard/engagements/${engagementId}/bba`, { state: { bbaProjectId: existingBbaProjectId } });
          } else {
            launchBba();
          }
        },
        startFresh: () => {
          setShowBbaDialog(false);
          launchBba(true);
        },
        cancelDialog: () => setShowBbaDialog(false),
      },
      strategy_workbook: {
        loading: swLoading,
        run: runStrategyWorkbook,
        dialog: {
          open: showSwDialog,
          title: 'Existing Strategy Workbook Found',
          description: `You have an existing Strategy Workbook (Status: ${
            existingSwStatus ? existingSwStatus.charAt(0).toUpperCase() + existingSwStatus.slice(1) : ''
          }). Would you like to continue where you left off, or start fresh?`,
          warning: 'Starting fresh will permanently delete all uploaded files and extracted data.',
        },
        continueExisting: () => {
          setShowSwDialog(false);
          dispatch(clearWorkbook());
          if (existingSwWorkbookId) {
            navigate(`/dashboard/engagements/${engagementId}/strategy-workbook`, { state: { workbookId: existingSwWorkbookId } });
          } else {
            launchSwWorkbook();
          }
        },
        startFresh: () => {
          setShowSwDialog(false);
          launchSwWorkbook(true);
        },
        cancelDialog: () => setShowSwDialog(false),
      },
      strategic_business_plan: {
        loading: sbpLoading,
        run: runSbp,
        dialog: {
          open: showSbpDialog,
          title: 'Existing Strategic Business Plan Found',
          description: `You have an existing Strategic Business Plan (Status: ${
            existingSbpStatus ? existingSbpStatus.charAt(0).toUpperCase() + existingSbpStatus.slice(1).replace(/_/g, ' ') : ''
          }). Would you like to continue where you left off, or start fresh?`,
          warning: 'Starting fresh will permanently delete all existing plan data.',
        },
        continueExisting: () => {
          setShowSbpDialog(false);
          if (existingSbpPlanId) {
            dispatch(clearPlan());
            navigate(`/dashboard/engagements/${engagementId}/strategic-business-plan`, { state: { sbpPlanId: existingSbpPlanId } });
          } else {
            launchSbp();
          }
        },
        startFresh: () => {
          setShowSbpDialog(false);
          launchSbp(true);
        },
        cancelDialog: () => setShowSbpDialog(false),
      },
    },
  };
}
