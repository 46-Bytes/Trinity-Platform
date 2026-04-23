import { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { ArrowLeft, FileText, Loader2, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { FileUploadPOC } from '@/components/poc/FileUploadPOC';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

type LaunchState = 'checking' | 'choose' | 'ready';

export default function FileUploadPOCPage() {
  const { engagementId } = useParams<{ engagementId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const stateProjectId = (location.state as { bbaProjectId?: string } | null)?.bbaProjectId;
  const queryProjectId = searchParams.get('project_id');

  const isStandalone = !engagementId;
  const hasIncomingProject = !!(stateProjectId || queryProjectId);

  const [launchState, setLaunchState] = useState<LaunchState>(
    isStandalone && !hasIncomingProject ? 'checking' : 'ready'
  );
  const [existingProject, setExistingProject] = useState<{
    id: string;
    max_step_reached?: number;
  } | null>(null);
  const [resolvedProjectId, setResolvedProjectId] = useState<string | undefined>(
    stateProjectId || queryProjectId || undefined
  );
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    if (launchState !== 'checking') return;
    const token = localStorage.getItem('auth_token');
    if (!token) { setLaunchState('ready'); return; }

    fetch(`${API_BASE_URL}/api/poc`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: 'include',
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => {
        const projects: Array<{ id: string; max_step_reached?: number }> = data.projects || [];
        const progressed = projects.find(p => (p.max_step_reached || 0) >= 2);
        if (progressed) {
          setExistingProject(progressed);
          setLaunchState('choose');
        } else {
          setLaunchState('ready');
        }
      })
      .catch(() => setLaunchState('ready'));
  }, [launchState]);

  const handleContinue = () => {
    if (existingProject) {
      setResolvedProjectId(existingProject.id);
      setLaunchState('ready');
    }
  };

  const handleStartNew = async () => {
    setIsCreating(true);
    const token = localStorage.getItem('auth_token');
    if (!token) { setIsCreating(false); return; }
    try {
      const res = await fetch(`${API_BASE_URL}/api/poc/create-project`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setResolvedProjectId(data.project_id);
      setLaunchState('ready');
    } catch {
      toast.error('Failed to create a new project');
    } finally {
      setIsCreating(false);
    }
  };

  if (launchState === 'checking') {
    return (
      <div className="container mx-auto py-8 px-2 flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (launchState === 'choose') {
    return (
      <div className="container mx-auto py-8 px-2 flex items-center justify-center min-h-[60vh]">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-3 w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center">
              <FileText className="w-6 h-6 text-accent" />
            </div>
            <CardTitle>Recommendations Report Builder</CardTitle>
            <CardDescription>
              You have an existing session in progress (Step {existingProject?.max_step_reached ?? 1} of 9).
              Would you like to continue or start fresh?
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button onClick={handleContinue} className="w-full">
              Continue Existing
            </Button>
            <Button variant="outline" onClick={handleStartNew} disabled={isCreating} className="w-full">
              {isCreating
                ? <Loader2 className="w-4 h-4 animate-spin mr-2" />
                : <Plus className="w-4 h-4 mr-2" />}
              Start New
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-2">
      <div className="mb-6">
        <div className="mb-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(engagementId ? `/dashboard/engagements/${engagementId}` : '/dashboard/ai-tools')}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            {engagementId ? 'Back to Engagement' : 'Back to AI Tools'}
          </Button>
        </div>
        <h1 className="text-3xl font-bold mb-2">Business Diagnostic Report Builder Tool</h1>
        <p className="text-muted-foreground">
          Use this tool to generate client diagnostic reports
        </p>
      </div>
      <FileUploadPOC engagementId={engagementId} initialProjectId={resolvedProjectId} />
    </div>
  );
}
