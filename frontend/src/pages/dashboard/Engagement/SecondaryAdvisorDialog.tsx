import { useState, useEffect, useMemo } from 'react';
import { X, Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from "sonner";
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { updateEngagement, fetchEngagements } from '@/store/slices/engagementReducer';
import { fetchFirmAdvisors } from '@/store/slices/firmReducer';
import { useAuth } from '@/context/AuthContext';
import type { Engagement, Advisor } from '@/store/slices/engagementReducer';
import type { Advisor as FirmAdvisor } from '@/store/slices/firmReducer';

interface SecondaryAdvisorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  engagement: Engagement | null;
  firmId?: string;
  statusFilter?: string;
  searchQuery?: string;
  onSuccess?: () => void;
}

export function SecondaryAdvisorDialog({
  open,
  onOpenChange,
  engagement,
  firmId,
  statusFilter,
  searchQuery,
  onSuccess,
}: SecondaryAdvisorDialogProps) {
  const dispatch = useAppDispatch();
  const { user } = useAuth();
  const { advisors: firmAdvisors, isLoading: isLoadingAdvisors } = useAppSelector((state) => state.firm);
  const [selectedSecondaryAdvisors, setSelectedSecondaryAdvisors] = useState<string[]>([]);

  // Get firm_id directly from user (firm_advisor always has firmId) or from prop
  const firmIdToUse = user?.firmId || firmId;

  // Fetch firm advisors when dialog opens
  useEffect(() => {
    if (open && firmIdToUse && user?.role === 'firm_advisor') {
      dispatch(fetchFirmAdvisors(firmIdToUse));
    }
  }, [open, firmIdToUse, user?.role, dispatch]);

  // Initialize selected advisors when engagement changes
  useEffect(() => {
    if (engagement) {
      setSelectedSecondaryAdvisors(engagement.assignedUsers || []);
    }
  }, [engagement]);

  // Reset when dialog closes
  useEffect(() => {
    if (!open) {
      setSelectedSecondaryAdvisors([]);
    }
  }, [open]);

  const handleSaveSecondaryAdvisors = async () => {
    if (!engagement) return;

    try {
      await dispatch(updateEngagement({
        id: engagement.id,
        updates: {
          assignedUsers: selectedSecondaryAdvisors,
        },
      })).unwrap();

      toast.success("Secondary advisors updated successfully!");
      onOpenChange(false);
      
      // Refetch engagements to get updated data
      dispatch(fetchEngagements({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: searchQuery || undefined,
        firm_id: firmId,
      }));

      onSuccess?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update secondary advisors");
    }
  };

  const handleAddSecondaryAdvisor = (advisorId: string) => {
    if (!selectedSecondaryAdvisors.includes(advisorId)) {
      setSelectedSecondaryAdvisors([...selectedSecondaryAdvisors, advisorId]);
    }
  };

  const handleRemoveSecondaryAdvisor = (advisorId: string) => {
    setSelectedSecondaryAdvisors(selectedSecondaryAdvisors.filter(id => id !== advisorId));
  };

  // Get all firm advisors from Redux store (fetched via fetchFirmAdvisors)
  const allFirmAdvisors = useMemo(() => {
    return (firmAdvisors || []).map((advisor: FirmAdvisor) => ({
      id: advisor.id,
      name: advisor.name,
    })) as Advisor[];
  }, [firmAdvisors]);

  // Get available advisors, excluding:
  // 1. The current user (primary advisor)
  // 2. Already selected secondary advisors
  const availableAdvisors = useMemo(() => {
    return allFirmAdvisors.filter((advisor: Advisor) => {
      // Exclude current user (primary advisor)
      if (user?.id && String(advisor.id) === String(user.id)) {
        return false;
      }
      // Exclude already selected secondary advisors
      return !selectedSecondaryAdvisors.some(id => String(id) === String(advisor.id));
    });
  }, [allFirmAdvisors, user?.id, selectedSecondaryAdvisors]);

  if (!engagement) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Manage Secondary Advisors</DialogTitle>
          <DialogDescription>
            Add or remove secondary advisors from this engagement. Only advisors from your firm can be added.
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Engagement</label>
            <p className="text-sm text-muted-foreground">{engagement.title}</p>
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">Current Secondary Advisors</label>
            {selectedSecondaryAdvisors.length === 0 ? (
              <p className="text-sm text-muted-foreground">No secondary advisors assigned</p>
            ) : (
              <div className="space-y-2">
                {selectedSecondaryAdvisors.map(advisorId => {
                  const advisor = allFirmAdvisors.find((a: Advisor) => String(a.id) === String(advisorId));
                  return advisor ? (
                    <div key={advisorId} className="flex items-center justify-between p-2 rounded-md border border-border">
                      <span className="text-sm">{advisor.name}</span>
                      <button
                        onClick={() => handleRemoveSecondaryAdvisor(advisorId)}
                        className="text-destructive hover:text-destructive/80 transition-colors"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ) : (
                    <div key={advisorId} className="flex items-center justify-between p-2 rounded-md border border-border">
                      <span className="text-sm text-muted-foreground">Unknown advisor ({advisorId})</span>
                      <button
                        onClick={() => handleRemoveSecondaryAdvisor(advisorId)}
                        className="text-destructive hover:text-destructive/80 transition-colors"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">Add Secondary Advisor</label>
            {!firmIdToUse ? (
              <p className="text-sm text-muted-foreground">Unable to determine firm. Please refresh the page.</p>
            ) : isLoadingAdvisors ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading advisors...
              </div>
            ) : availableAdvisors.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {allFirmAdvisors.length === 0
                  ? "No advisors available in your firm"
                  : allFirmAdvisors.length === 1 && String(allFirmAdvisors[0]?.id) === String(user?.id)
                  ? "You are the only advisor in your firm"
                  : "No available advisors to add (all advisors are already assigned)"}
              </p>
            ) : (
              <Select onValueChange={handleAddSecondaryAdvisor}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an advisor to add" />
                </SelectTrigger>
                <SelectContent>
                  {availableAdvisors.map((advisor: Advisor) => (
                    <SelectItem key={advisor.id} value={advisor.id}>
                      {advisor.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <button
              onClick={() => onOpenChange(false)}
              className="px-4 py-2 text-sm rounded-md border border-border hover:bg-muted transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveSecondaryAdvisors}
              className="btn-primary px-4 py-2 text-sm"
            >
              Save Changes
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

