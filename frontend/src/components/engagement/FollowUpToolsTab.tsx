/**
 * Follow-up tools tab for an engagement.
 * Lists completed diagnostics and allows running BBA Builder (and future tools) from any of them.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText, Loader2, Wrench } from 'lucide-react';
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
  const [loadingDiagnosticId, setLoadingDiagnosticId] = useState<string | null>(null);

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

  const runBbaBuilder = async (diagnosticId: string) => {
    setLoadingDiagnosticId(diagnosticId);
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        toast.error('Not authenticated');
        return;
      }
      const res = await fetch(
        `${API_BASE_URL}/api/poc/create-from-diagnostic?diagnostic_id=${diagnosticId}`,
        { method: 'POST', headers: { Authorization: `Bearer ${token}` }, credentials: 'include' }
      );
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
      setLoadingDiagnosticId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Wrench className="h-5 w-5 text-muted-foreground" />
          Follow-up tools
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Run additional tools using your completed diagnostics. Each tool uses a selected diagnostic as context.
        </p>
      </div>

      {visibleDiagnostics.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground text-center py-8">
              No completed diagnostics yet. Complete a diagnostic in the <strong>Diagnostic</strong> tab to run follow-up tools here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
          {visibleDiagnostics.map((diagnostic) => {
            const tag = diagnosticTags[diagnostic.id] ?? diagnostic.tag ?? (diagnostic as any).tag;
            const completedAt = diagnostic.completed_at ?? (diagnostic as any).completedAt;
            const isLoading = loadingDiagnosticId === diagnostic.id;

            return (
              <Card key={diagnostic.id} className="flex flex-col">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base font-medium">
                    {tag && String(tag).trim() ? tag : 'Diagnostic report'}
                  </CardTitle>
                  <CardDescription>
                    Completed {formatDate(completedAt)}
                  </CardDescription>
                </CardHeader>
                <CardContent className="mt-auto pt-4">
                  <Button
                    variant="outline"
                    className="w-full sm:w-auto"
                    disabled={!!loadingDiagnosticId}
                    onClick={() => runBbaBuilder(diagnostic.id)}
                  >
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <FileText className="h-4 w-4 mr-2" />
                    )}
                    BBA Builder
                  </Button>
                  <p className="text-xs text-muted-foreground mt-2">
                    Build on this diagnostic with the BBA report builder.
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
