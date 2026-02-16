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
import { updateEngagement, fetchEngagements, fetchSecondaryAdvisorCandidates } from '@/store/slices/engagementReducer';
import { useAuth } from '@/context/AuthContext';
import type { Engagement, Advisor, SecondaryAdvisorCandidate } from '@/store/slices/engagementReducer';

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
  const { secondaryAdvisorCandidates, isLoadingCandidates } = useAppSelector((state) => state.engagement);
  const [selectedSecondaryAdvisors, setSelectedSecondaryAdvisors] = useState<string[]>([]);

  // Fetch secondary advisor candidates when dialog opens
  useEffect(() => {
    if (open && engagement?.id) {
      dispatch(fetchSecondaryAdvisorCandidates(engagement.id));
    }
  }, [open, engagement?.id, dispatch]);

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

  // Get available advisors, excluding already selected secondary advisors
  const availableAdvisors = useMemo(() => {
    return (secondaryAdvisorCandidates || []).filter((candidate: SecondaryAdvisorCandidate) => {
      // Exclude already selected secondary advisors
      return !selectedSecondaryAdvisors.some(id => String(id) === String(candidate.id));
    });
  }, [secondaryAdvisorCandidates, selectedSecondaryAdvisors]);

  // Create a map of all candidates (including selected ones) for display
  const allCandidatesMap = useMemo(() => {
    const map = new Map<string, SecondaryAdvisorCandidate>();
    (secondaryAdvisorCandidates || []).forEach((candidate: SecondaryAdvisorCandidate) => {
      map.set(candidate.id, candidate);
    });
    return map;
  }, [secondaryAdvisorCandidates]);

  if (!engagement) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Manage Secondary Advisors</DialogTitle>
          <DialogDescription>
            Add or remove secondary advisors (co-advisors) from this engagement. 
            Eligible advisors will be shown based on the engagement context.
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
                  const candidate = allCandidatesMap.get(advisorId);
                  return candidate ? (
                    <div key={advisorId} className="flex items-center justify-between p-2 rounded-md border border-border">
                      <span className="text-sm">{candidate.name}</span>
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
            {isLoadingCandidates ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading advisors...
              </div>
            ) : availableAdvisors.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {secondaryAdvisorCandidates.length === 0
                  ? "No eligible advisors available to add"
                  : "No available advisors to add (all eligible advisors are already assigned)"}
              </p>
            ) : (
              <Select onValueChange={handleAddSecondaryAdvisor}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an advisor to add" />
                </SelectTrigger>
                <SelectContent>
                  {availableAdvisors.map((candidate: SecondaryAdvisorCandidate) => (
                    <SelectItem key={candidate.id} value={candidate.id}>
                      {candidate.name}
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

