/**
 * Follow-up tools tab for an engagement.
 * Always shows BBA Builder and Strategy Workbook tools.
 * If a completed diagnostic exists, it can optionally be used as context.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch } from '@/store/hooks';
import { clearWorkbook } from '@/store/slices/strategyWorkbookReducer';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { BookOpen, FileText, Loader2, Wrench } from 'lucide-react';
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

  const anyLoading = bbaLoading || swLoading;

  const getAuthToken = () => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      toast.error('Not authenticated');
      return null;
    }
    return token;
  };

  const runBbaBuilder = async () => {
    setBbaLoading(true);
    try {
      const token = getAuthToken();
      if (!token) return;

      let url: string;
      if (effectiveDiagnosticId) {
        url = `${API_BASE_URL}/api/poc/create-from-diagnostic?diagnostic_id=${effectiveDiagnosticId}`;
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
              Report and Recommendation Builder
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
              Run BBA Builder
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
      </div>
    </div>
  );
}
