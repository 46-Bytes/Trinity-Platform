import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  fetchAssociations,
  createAssociation,
  deleteAssociation,
  type AdvisorClientAssociation,
} from '@/store/slices/advisorClientReducer';
import { fetchUsers, type User } from '@/store/slices/userReducer';
import { fetchFirmClientsById, type Client } from '@/store/slices/firmReducer';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Plus, Trash2, Search } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

// Union type to support both User and Advisor types
type AdvisorLike = User | (User & { firm_id?: string });

interface AdvisorClientDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  advisor: AdvisorLike;
  firmClients?: Client[];
}

export function AdvisorClientDialog({ open, onOpenChange, advisor, firmClients }: AdvisorClientDialogProps) {
  const dispatch = useAppDispatch();
  const { associations, isLoading, isCreating, isDeleting, error } = useAppSelector(
    (state) => state.advisorClient
  );
  const { users } = useAppSelector((state) => state.user);
  const { clients: firmClientsFromStore } = useAppSelector((state) => state.firm);

  const [searchQuery, setSearchQuery] = useState('');
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [selectedClientId, setSelectedClientId] = useState<string>('');

  // Check if advisor has firm_id (for firm advisors)
  const advisorFirmId = 'firm_id' in advisor ? advisor.firm_id : undefined;

  // Determine which clients to use: prop > store > fetch
  const clientsToUse = firmClients || (advisorFirmId ? firmClientsFromStore : null);

  // Fetch associations when dialog opens
  useEffect(() => {
    if (open && advisor.id) {
      dispatch(fetchAssociations(advisor.id));
    }
  }, [open, advisor.id, dispatch]);

  // Fetch firm clients if advisor has firm_id but firmClients not provided
  useEffect(() => {
    if (open && advisorFirmId && !firmClients && firmClientsFromStore.length === 0) {
      dispatch(fetchFirmClientsById(advisorFirmId));
    }
  }, [open, advisorFirmId, firmClients, firmClientsFromStore.length, dispatch]);

  // Fetch users if not already loaded and not using firm clients
  useEffect(() => {
    if (open && users.length === 0 && !clientsToUse) {
      dispatch(fetchUsers());
    }
  }, [open, users.length, dispatch, clientsToUse]);

  // Show error toast
  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  // Get clients that are not yet associated with this advisor
  const associatedClientIds = new Set(associations.map((assoc) => assoc.client_id));
  
  // Get set of firm client IDs to exclude for regular advisors
  const firmClientIds = new Set(firmClientsFromStore.map((c) => c.id));
  
  // Use firmClients if provided or available in store, otherwise use users from store
  let availableClients: Array<User | Client>;
  
  if (clientsToUse) {
    availableClients = clientsToUse.filter(
      (client) => !associatedClientIds.has(client.id)
    );
  } else {
    availableClients = users.filter(
      (user) => 
        user.role === 'client' && 
        !associatedClientIds.has(user.id) &&
        !firmClientIds.has(user.id)  // Exclude clients that belong to firms
    );
  }

  // Helper function to get client details
  const getClientDetails = (association: AdvisorClientAssociation) => {
    // First try to get from association data
    if (association.client_email || association.client_name) {
      return {
        email: association.client_email || '',
        name: association.client_name || '',
      };
    }
    if (clientsToUse) {
      const client = clientsToUse.find((c) => c.id === association.client_id);
      if (client) {
        return {
          email: client.email,
          name: client.name,
        };
      }
    }
    // Fallback to users store
    const client = users.find((u) => u.id === association.client_id);
    if (client) {
      return {
        email: client.email,
        name: client.name,
      };
    }
    return {
      email: 'Unknown Client',
      name: '',
    };
  };

  // Filter available clients by search query
  const filteredAvailableClients = availableClients.filter(
    (client) =>
      client.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      client.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCreateAssociation = async () => {
    if (!selectedClientId) {
      toast.error('Please select a client');
      return;
    }

    try {
      await dispatch(
        createAssociation({
          advisorId: advisor.id,
          clientId: selectedClientId,
        })
      ).unwrap();
      toast.success('Client associated successfully');
      setShowAddDialog(false);
      setSelectedClientId('');
      setSearchQuery('');
      // Refetch associations to get the full data with user details
      dispatch(fetchAssociations(advisor.id));
    } catch (error) {
      // Error is handled by the reducer and shown in toast
    }
  };

  const handleDeleteAssociation = async (associationId: string) => {
    try {
      await dispatch(deleteAssociation(associationId)).unwrap();
      toast.success('Association removed successfully');
    } catch (error) {
      // Error is handled by the reducer and shown in toast
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Client Associations</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 mt-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-accent" />
                <span className="ml-2 text-muted-foreground">Loading associations...</span>
              </div>
            ) : associations.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p>No clients associated with this advisor.</p>
                <p className="text-sm mt-2">Click "Add Client" to create an association.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {associations.map((association) => {
                  const clientDetails = getClientDetails(association);
                  return (
                    <div
                      key={association.id}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
                    >
                      <div className="flex-1">
                        <p className="font-medium">{clientDetails.email}</p>
                        {clientDetails.name && clientDetails.name !== clientDetails.email && (
                          <p className="text-sm text-muted-foreground">{clientDetails.name}</p>
                        )}
                      </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteAssociation(association.id)}
                      disabled={isDeleting}
                      className="text-destructive hover:text-destructive hover:bg-destructive/10"
                    >
                      {isDeleting ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Add Client Button at Bottom Right */}
          <div className="flex justify-end pt-4 border-t">
            <Button
              onClick={() => setShowAddDialog(true)}
              disabled={isCreating}
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Client
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add Client Association</DialogTitle>
            <DialogDescription>
              Select a client to associate with {advisor.name || advisor.email}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search clients by name or email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            <div className="max-h-[300px] overflow-y-auto border rounded-lg bg-background">
              {filteredAvailableClients.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">
                  {searchQuery ? (
                    <p>No clients found matching your search.</p>
                  ) : (
                    <p>All available clients are already associated.</p>
                  )}
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {filteredAvailableClients.map((client) => (
                    <button
                      key={client.id}
                      onClick={() => setSelectedClientId(client.id)}
                      className={cn(
                        'w-full p-3 text-left hover:bg-muted transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
                        selectedClientId === client.id && 'bg-muted'
                      )}
                    >
                      <p className="font-medium text-foreground">{client.email}</p>
                      {client.name && client.name !== client.email && (
                        <p className="text-sm text-muted-foreground mt-1">{client.name}</p>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button
              variant="outline"
              onClick={() => {
                setShowAddDialog(false);
                setSelectedClientId('');
                setSearchQuery('');
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateAssociation}
              disabled={isCreating || !selectedClientId}
            >
              {isCreating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                'Add Association'
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

