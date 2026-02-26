import { useState } from 'react';
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
import { useAppDispatch } from '@/store/hooks';
import { revokeFirm, fetchFirms } from '@/store/slices/firmReducer';
import { toast } from 'sonner';

interface RevokeFirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  firmId: string | null;
  firmName: string | null;
  onSuccess?: () => void;
}

export function RevokeFirmDialog({
  open,
  onOpenChange,
  firmId,
  firmName,
  onSuccess,
}: RevokeFirmDialogProps) {
  const dispatch = useAppDispatch();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleConfirmRevoke = async () => {
    if (!firmId) return;
    
    setIsSubmitting(true);
    try {
      await dispatch(revokeFirm(firmId)).unwrap();
      toast.success('Firm revoked successfully');
      dispatch(fetchFirms());
      onOpenChange(false);
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to revoke firm');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Revoke Firm</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to revoke <strong>{firmName}</strong>? 
            This will prevent all firm users (firm admins, advisors, and clients) from logging in. 
            You can reactivate the firm later if needed.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirmRevoke}
            disabled={isSubmitting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isSubmitting ? 'Revoking...' : 'Revoke Firm'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}


