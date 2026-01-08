import { useEffect } from 'react';
import { useParams, Outlet, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Building2 } from 'lucide-react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchFirmById } from '@/store/slices/firmReducer';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useAuth } from '@/context/AuthContext';

export default function FirmDetailsLayout() {
  const { firmId } = useParams<{ firmId: string }>();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { firm, isLoading, error } = useAppSelector((state) => state.firm);
  const { user } = useAuth();

  // Check if user is superadmin
  const isSuperAdmin = user?.role === 'super_admin';

  useEffect(() => {
    if (!isSuperAdmin) {
      toast.error('Access denied. Super admin privileges required.');
      navigate('/dashboard/firms');
      return;
    }

    if (firmId) {
      dispatch(fetchFirmById(firmId));
    }
  }, [dispatch, firmId, isSuperAdmin, navigate]);

  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  if (!isSuperAdmin) {
    return null;
  }

  if (isLoading && !firm) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-accent" />
        <span className="ml-2 text-muted-foreground">Loading firm details...</span>
      </div>
    );
  }

  if (error && !firm) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          onClick={() => navigate('/dashboard/firms')}
          className="flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Firms
        </Button>
        <div className="card-trinity p-6">
          <div className="text-center py-12">
            <p className="text-destructive mb-2">Error loading firm</p>
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!firm) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          onClick={() => navigate('/dashboard/firms')}
          className="flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Firms
        </Button>
        <div className="card-trinity p-6">
          <div className="text-center py-12">
            <p className="text-muted-foreground">Firm not found</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          onClick={() => navigate('/dashboard/firms')}
          className="flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Firms
        </Button>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-heading text-2xl font-bold text-foreground">{firm.firm_name}</h1>
            <p className="text-sm text-muted-foreground">Firm ID: {firm.id.slice(0, 8)}...</p>
          </div>
        </div>
      </div>

      <Outlet context={{ firmId }} />
    </div>
  );
}

