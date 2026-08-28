/**
 * Shared "run this tool" launch logic for BBA / Strategy Workbook / Strategic
 * Business Plan / Roles Matrix / PD Scorecard: check for an existing
 * in-progress project for the engagement, surface a "Continue vs Start
 * Fresh" confirmation when found, otherwise create (optionally from the
 * most recent completed diagnostic) and navigate to the tool's route.
 *
 * Extracted from FollowUpToolsTab.tsx so the Program Guide module card can
 * reuse the exact same behavior instead of re-implementing it.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch } from '@/store/hooks';
import { clearWorkbook } from '@/store/slices/strategyWorkbookReducer';
import { clearPlan } from '@/store/slices/strategicBusinessPlanReducer';
import { clearMatrix } from '@/store/slices/rolesMatrixReducer';
import { clearBuild } from '@/store/slices/pdScorecardReducer';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export type ToolKey = 'bba' | 'strategy_workbook' | 'strategic_business_plan' | 'roles_matrix' | 'pd_scorecard';

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

  const [rmLoading, setRmLoading] = useState(false);
  const [showRmDialog, setShowRmDialog] = useState(false);
  const [existingRmMatrixId, setExistingRmMatrixId] = useState<string | null>(null);
  const [existingRmStatus, setExistingRmStatus] = useState<string>('');

  const [pdLoading, setPdLoading] = useState(false);
  const [showPdDialog, setShowPdDialog] = useState(false);
  const [existingPdBuildId, setExistingPdBuildId] = useState<string | null>(null);
  const [existingPdStatus, setExistingPdStatus] = useState<string>('');

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

  const anyLoading = bbaLoading || swLoading || sbpLoading || rmLoading || pdLoading;

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

  // ---- Roles & Responsibilities Matrix ----
  const launchRolesMatrix = async (forceNew: boolean = false) => {
    setRmLoading(true);
    try {
      const token = getAuthToken();
      if (!token) return;

      // Start Fresh discards the previous matrix so the pre-flight stops finding it
      if (forceNew && existingRmMatrixId) {
        await fetch(`${API_BASE_URL}/api/roles-matrix/${existingRmMatrixId}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
          credentials: 'include',
        });
      }

      const res = await fetch(`${API_BASE_URL}/api/roles-matrix/create-project?engagement_id=${engagementId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Failed to create roles matrix' }));
        toast.error(err.detail || 'Failed to start Roles & Responsibilities Matrix');
        return;
      }
      const data = await res.json();
      const matrixId = data.matrix_id;
      if (matrixId) {
        dispatch(clearMatrix());
        navigate(`/dashboard/engagements/${engagementId}/roles-matrix`, { state: { matrixId } });
      } else {
        toast.error('Invalid response from server');
      }
    } catch (e) {
      console.error(e);
      toast.error('Failed to start Roles & Responsibilities Matrix');
    } finally {
      setRmLoading(false);
    }
  };

  const runRolesMatrix = async () => {
    const token = getAuthToken();
    if (!token) return;

    setRmLoading(true);
    // Pre-check for an existing matrix so the choice is made here, not after navigating
    try {
      const listRes = await fetch(`${API_BASE_URL}/api/roles-matrix/?engagement_id=${engagementId}`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (listRes.ok) {
        const listData = await listRes.json();
        const matrices: Array<{ id: string; status: string }> = listData.matrices || [];
        const existing = matrices[0]; // most recent, ordered by updated_at desc
        if (existing) {
          setExistingRmStatus(existing.status);
          setExistingRmMatrixId(existing.id);
          setShowRmDialog(true);
          setRmLoading(false);
          return;
        }
      }
    } catch {
      // If the pre-check fails, fall through to normal creation
    }

    await launchRolesMatrix();
  };

  // ---- PD & Role Scorecards ----
  const launchPDScorecard = async (forceNew: boolean = false) => {
    setPdLoading(true);
    try {
      const token = getAuthToken();
      if (!token) return;

      // Start Fresh discards the previous build so the pre-flight stops finding it
      if (forceNew && existingPdBuildId) {
        await fetch(`${API_BASE_URL}/api/pd-scorecard/${existingPdBuildId}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
          credentials: 'include',
        });
      }

      const res = await fetch(`${API_BASE_URL}/api/pd-scorecard/create-project?engagement_id=${engagementId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Failed to create PD & scorecard build' }));
        toast.error(err.detail || 'Failed to start PD & Role Scorecards');
        return;
      }
      const data = await res.json();
      const buildId = data.build_id;
      if (buildId) {
        dispatch(clearBuild());
        navigate(`/dashboard/engagements/${engagementId}/pd-scorecard`, { state: { buildId } });
      } else {
        toast.error('Invalid response from server');
      }
    } catch (e) {
      console.error(e);
      toast.error('Failed to start PD & Role Scorecards');
    } finally {
      setPdLoading(false);
    }
  };

  const runPDScorecard = async () => {
    const token = getAuthToken();
    if (!token) return;

    setPdLoading(true);
    // Pre-check for an existing build so the choice is made here, not after navigating
    try {
      const listRes = await fetch(`${API_BASE_URL}/api/pd-scorecard/?engagement_id=${engagementId}`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (listRes.ok) {
        const listData = await listRes.json();
        const builds: Array<{ id: string; status: string }> = listData.builds || [];
        const existing = builds[0]; // most recent, ordered by updated_at desc
        if (existing) {
          setExistingPdStatus(existing.status);
          setExistingPdBuildId(existing.id);
          setShowPdDialog(true);
          setPdLoading(false);
          return;
        }
      }
    } catch {
      // If the pre-check fails, fall through to normal creation
    }

    await launchPDScorecard();
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
      roles_matrix: {
        loading: rmLoading,
        run: runRolesMatrix,
        dialog: {
          open: showRmDialog,
          title: 'Existing Roles Matrix Found',
          description: `You have an existing Roles & Responsibilities Matrix (Status: ${
            existingRmStatus ? existingRmStatus.charAt(0).toUpperCase() + existingRmStatus.slice(1).replace(/_/g, ' ') : ''
          }). Would you like to continue where you left off, or start fresh?`,
          warning: 'Starting fresh will permanently delete all uploaded files and extracted data.',
        },
        continueExisting: () => {
          setShowRmDialog(false);
          dispatch(clearMatrix());
          if (existingRmMatrixId) {
            navigate(`/dashboard/engagements/${engagementId}/roles-matrix`, { state: { matrixId: existingRmMatrixId } });
          } else {
            launchRolesMatrix();
          }
        },
        startFresh: () => {
          setShowRmDialog(false);
          launchRolesMatrix(true);
        },
        cancelDialog: () => setShowRmDialog(false),
      },
      pd_scorecard: {
        loading: pdLoading,
        run: runPDScorecard,
        dialog: {
          open: showPdDialog,
          title: 'Existing PD & Scorecard Build Found',
          description: `You have an existing PD & Role Scorecards build (Status: ${
            existingPdStatus ? existingPdStatus.charAt(0).toUpperCase() + existingPdStatus.slice(1).replace(/_/g, ' ') : ''
          }). Would you like to continue where you left off, or start fresh?`,
          warning: 'Starting fresh will permanently delete all uploaded files, roles and approved drafts.',
        },
        continueExisting: () => {
          setShowPdDialog(false);
          dispatch(clearBuild());
          if (existingPdBuildId) {
            navigate(`/dashboard/engagements/${engagementId}/pd-scorecard`, { state: { buildId: existingPdBuildId } });
          } else {
            launchPDScorecard();
          }
        },
        startFresh: () => {
          setShowPdDialog(false);
          launchPDScorecard(true);
        },
        cancelDialog: () => setShowPdDialog(false),
      },
    },
  };
}
