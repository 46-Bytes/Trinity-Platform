import { useAuth } from '@/context/AuthContext';
import { AlertTriangle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export function ImpersonationBanner() {
  const { isImpersonating, user, originalUser, stopImpersonation } = useAuth();

  if (!isImpersonating || !user || !originalUser) {
    return null;
  }

  const handleStopImpersonation = async () => {
    try {
      await stopImpersonation();
      toast.success('Impersonation stopped. Returned to your account.');
    } catch (error) {
      toast.error('Failed to stop impersonation. Please try again.');
      console.error('Error stopping impersonation:', error);
    }
  };

  return (
    <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-yellow-800">
              You are impersonating <span className="font-semibold">{user.name}</span> ({user.email})
            </p>
            <p className="text-xs text-yellow-700 mt-0.5">
              Original account: {originalUser.name} ({originalUser.email})
            </p>
          </div>
        </div>
        <Button
          onClick={handleStopImpersonation}
          variant="outline"
          size="sm"
          className="bg-white hover:bg-yellow-100 border-yellow-300 text-yellow-800"
        >
          <X className="w-4 h-4 mr-2" />
          Stop Impersonation
        </Button>
      </div>
    </div>
  );
}

