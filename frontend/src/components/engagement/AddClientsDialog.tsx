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
import { addClientsToEngagement, removeClientFromEngagement, fetchEngagements, fetchUserRoleData } from '@/store/slices/engagementReducer';
import { useAuth } from '@/context/AuthContext';
import type { Engagement, Client } from '@/store/slices/engagementReducer';

interface AddClientsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  engagement: Engagement | null;
  firmId?: string;
  statusFilter?: string;
  searchQuery?: string;
  onSuccess?: () => void;
}

export function AddClientsDialog({
  open,
  onOpenChange,
  engagement,
  firmId,
  statusFilter,
  searchQuery,
  onSuccess,
}: AddClientsDialogProps) {
  const dispatch = useAppDispatch();
  const { user } = useAuth();
  const { userRoleData, isLoading, engagements } = useAppSelector((state) => state.engagement);
  const [selectedClientToAdd, setSelectedClientToAdd] = useState<string>('');

  // IMPORTANT: `engagement` comes from parent component local state (selectedEngagement).
  // After we refetch engagements, the store updates but the parent-selected object can remain stale.
  // So we always render from the freshest engagement in the Redux store (by id).
  const effectiveEngagement = useMemo(() => {
    if (!engagement) return null;
    return engagements.find((e) => String(e.id) === String(engagement.id)) ?? engagement;
  }, [engagement, engagements]);

  // Fetch user role data when dialog opens to get eligible clients
  useEffect(() => {
    if (open) {
      dispatch(fetchUserRoleData());
    }
  }, [open, dispatch]);

  // Reset when dialog closes
  useEffect(() => {
    if (!open) {
      setSelectedClientToAdd('');
    }
  }, [open]);

  // Get eligible clients from user role data
  const eligibleClients = useMemo(() => {
    if (!userRoleData?.clients) return [];
    return userRoleData.clients;
  }, [userRoleData]);

  // Get current clients in engagement
  const currentClientIds = useMemo(() => {
    if (!effectiveEngagement) return [];
    return effectiveEngagement.clientIds || (effectiveEngagement.clientId ? [effectiveEngagement.clientId] : []);
  }, [effectiveEngagement]);

  // Get available clients (not already in engagement)
  const availableClients = useMemo(() => {
    return eligibleClients.filter((client: Client) => {
      return !currentClientIds.some(id => String(id) === String(client.id));
    });
  }, [eligibleClients, currentClientIds]);

  // Get current clients with names for display
  const currentClients = useMemo(() => {
    if (!effectiveEngagement) return [];
    const clientNames =
      effectiveEngagement.clientNames || (effectiveEngagement.clientName ? [effectiveEngagement.clientName] : []);
    const clientIds = effectiveEngagement.clientIds || (effectiveEngagement.clientId ? [effectiveEngagement.clientId] : []);
    
    return clientIds.map((id, index) => ({
      id: String(id),
      name: clientNames[index] || 'Unknown Client',
    }));
  }, [effectiveEngagement]);

  const handleAddClient = async () => {
    if (!effectiveEngagement || !selectedClientToAdd) return;

    try {
      await dispatch(addClientsToEngagement({
        engagementId: effectiveEngagement.id,
        clientIds: [selectedClientToAdd],
      })).unwrap();

      toast.success("Client added successfully!");
      setSelectedClientToAdd('');
      
      // Refetch engagements to get updated data
      dispatch(fetchEngagements({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: searchQuery || undefined,
        firm_id: firmId,
      }));

      onSuccess?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to add client");
    }
  };

  const handleRemoveClient = async (clientId: string) => {
    if (!effectiveEngagement) return;

    // Don't allow removing the last client
    if (currentClientIds.length <= 1) {
      toast.error("Cannot remove the last client from an engagement");
      return;
    }

    try {
      await dispatch(removeClientFromEngagement({
        engagementId: effectiveEngagement.id,
        clientId: clientId,
      })).unwrap();

      toast.success("Client removed successfully!");
      
      // Refetch engagements to get updated data
      dispatch(fetchEngagements({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: searchQuery || undefined,
        firm_id: firmId,
      }));

      onSuccess?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to remove client");
    }
  };

  if (!effectiveEngagement) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Manage Clients</DialogTitle>
          <DialogDescription>
            Add or remove clients from this engagement. 
            Eligible clients will be shown based on your role and permissions.
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Engagement</label>
            <p className="text-sm text-muted-foreground">{effectiveEngagement.title}</p>
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">Current Clients</label>
            {currentClients.length === 0 ? (
              <p className="text-sm text-muted-foreground">No clients assigned</p>
            ) : (
              <div className="space-y-2">
                {currentClients.map((client) => (
                  <div key={client.id} className="flex items-center justify-between p-2 rounded-md border border-border">
                    <span className="text-sm">{client.name}</span>
                    {currentClients.length > 1 && (
                      <button
                        onClick={() => handleRemoveClient(client.id)}
                        className="text-destructive hover:text-destructive/80 transition-colors"
                        title="Remove client"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">Add Client</label>
            {isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading clients...
              </div>
            ) : availableClients.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {eligibleClients.length === 0
                  ? "No eligible clients available to add"
                  : "No available clients to add (all eligible clients are already in this engagement)"}
              </p>
            ) : (
              <div className="flex gap-2">
                <Select value={selectedClientToAdd} onValueChange={setSelectedClientToAdd}>
                  <SelectTrigger className="flex-1">
                    <SelectValue placeholder="Select a client to add" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableClients.map((client: Client) => (
                      <SelectItem key={client.id} value={client.id}>
                        {client.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <button
                  onClick={handleAddClient}
                  disabled={!selectedClientToAdd}
                  className="btn-primary px-4 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Add
                </button>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <button
              onClick={() => onOpenChange(false)}
              className="px-4 py-2 text-sm rounded-md border border-border hover:bg-muted transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

