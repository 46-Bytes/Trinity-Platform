import { useState } from 'react';
import { CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, Target, TrendingUp, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { useAppDispatch } from '@/store/hooks';
import { clearDiagnostic, fetchDiagnosticByEngagement } from '@/store/slices/diagnosticReducer';
import { ValueMovementView } from './ValueMovementView';
import type { ProgramGuideModule, ValueMovement } from '@/store/slices/programGuideReducer';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const SECTION_LABEL_CLASS = 'flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary mb-2';

interface RetakeDiagnosticCardProps {
  module: ProgramGuideModule;
  engagementId: string;
  currentUserId?: string | null;
  valueMovement: ValueMovement | null;
  onNavigateToDiagnostic: () => void;
}

export function RetakeDiagnosticCard({
  module,
  engagementId,
  currentUserId,
  valueMovement,
  onNavigateToDiagnostic,
}: RetakeDiagnosticCardProps) {
  const dispatch = useAppDispatch();
  const [isRetaking, setIsRetaking] = useState(false);

  const handleRetake = async () => {
    if (!currentUserId) {
      toast.error('Not authenticated');
      return;
    }
    const token = localStorage.getItem('auth_token');
    if (!token) {
      toast.error('Not authenticated');
      return;
    }

    setIsRetaking(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/diagnostics/create`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          engagement_id: engagementId,
          created_by_user_id: currentUserId,
          questions: {},
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Failed to start a new diagnostic' }));
        toast.error(err.detail || 'Failed to start a new diagnostic');
        return;
      }

      dispatch(clearDiagnostic());
      dispatch(fetchDiagnosticByEngagement(engagementId));
      onNavigateToDiagnostic();
    } catch (e) {
      console.error(e);
      toast.error('Failed to start a new diagnostic');
    } finally {
      setIsRetaking(false);
    }
  };

  return (
    <div className="card-trinity overflow-hidden">
      <CardContent className="space-y-5 pt-6">
        {module.purpose && (
          <div>
            <p className={SECTION_LABEL_CLASS}>
              <Target className="h-3.5 w-3.5" />
              Purpose
            </p>
            <p className="text-sm text-muted-foreground">{module.purpose}</p>
          </div>
        )}

        <div>
          <p className={SECTION_LABEL_CLASS}>
            <TrendingUp className="h-3.5 w-3.5" />
            Value Movement
          </p>
          <ValueMovementView valueMovement={valueMovement} />
        </div>

        <Button onClick={handleRetake} disabled={isRetaking}>
          {isRetaking ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
          Retake Diagnostic
        </Button>
      </CardContent>
    </div>
  );
}
