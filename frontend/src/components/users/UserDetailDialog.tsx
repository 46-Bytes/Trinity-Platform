import { Mail, CheckCircle, XCircle, Calendar } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { roleLabels, roleColors } from '@/types/auth';
import type { User } from '@/store/slices/userReducer';
import { useAuth } from '@/context/AuthContext';

interface UserDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: User | null;
}

const formatDate = (dateString: string) => {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return 'N/A';
  }
};

export function UserDetailDialog({ open, onOpenChange, user }: UserDetailDialogProps) {
  const { user: currentUser } = useAuth();

  if (!user) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>User Details</DialogTitle>
          <DialogDescription>
            View detailed information about the user
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 mt-4">
          <div className="flex items-center gap-3 pb-4 border-b">
            <div className="w-12 h-12 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-medium text-lg">
              {user.name?.charAt(0) || 'U'}
            </div>
            <div>
              <h3 className="font-semibold text-lg">{user.name || 'Unnamed User'}</h3>
              <p className="text-sm text-muted-foreground">{user.email}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Role</Label>
              <div className="flex items-center gap-2">
                <span className={cn("status-badge", roleColors[user.role])}>
                  {currentUser?.role === 'super_admin' 
                    ? (user.role === 'client' && user.firm_id 
                        ? 'Firm Client' 
                        : roleLabels[user.role])
                    : roleLabels[user.role]}
                </span>
              </div>
            </div>

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Status</Label>
              <div className="flex items-center gap-2">
                <span className={cn(
                  "status-badge",
                  user.is_active ? "status-success" : "bg-muted text-muted-foreground"
                )}>
                  {user.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            </div>

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Email Verified</Label>
              <div className="flex items-center gap-2">
                {user.email_verified ? (
                  <span className="status-badge status-success flex items-center gap-1 w-fit">
                    <CheckCircle className="w-3 h-3" />
                    Verified
                  </span>
                ) : (
                  <span className="status-badge bg-yellow-100 text-yellow-800 flex items-center gap-1 w-fit">
                    <XCircle className="w-3 h-3" />
                    Unverified
                  </span>
                )}
              </div>
            </div>

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Last Login</Label>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-muted-foreground" />
                <p className="text-sm font-medium">
                  {user.last_login ? formatDate(user.last_login) : 'Never'}
                </p>
              </div>
            </div>

            <div className="space-y-1 sm:col-span-2">
              <Label className="text-xs text-muted-foreground">Email</Label>
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-muted-foreground" />
                <p className="text-sm font-medium">{user.email}</p>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

