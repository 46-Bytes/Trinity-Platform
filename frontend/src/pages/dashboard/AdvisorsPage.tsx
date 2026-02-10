import { useState, useEffect } from 'react';
import { Search, Plus, Trash2, X, AlertTriangle, User, Mail } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchFirm, fetchFirmAdvisors, addAdvisorToFirm, removeAdvisorFromFirm, getAdvisorEngagements, suspendAdvisor, reactivateAdvisor, fetchFirmClients } from '@/store/slices/firmReducer';
import AdvisorList from './advisors/AdvisorList';
import { AdvisorClientDialog } from '@/components/users/AdvisorClientDialog';
import type { Advisor } from '@/store/slices/firmReducer';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
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
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';

export default function AdvisorsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [advisorToDelete, setAdvisorToDelete] = useState<string | null>(null);
  const [suspendDialogOpen, setSuspendDialogOpen] = useState(false);
  const [advisorToSuspend, setAdvisorToSuspend] = useState<string | null>(null);
  const [advisorEngagements, setAdvisorEngagements] = useState<{ primary: any[]; secondary: any[] } | null>(null);
  const [reassignments, setReassignments] = useState<Record<string, string>>({});
  const [isLoadingEngagements, setIsLoadingEngagements] = useState(false);
  const [associateDialogOpen, setAssociateDialogOpen] = useState(false);
  const [selectedAdvisorForAssociation, setSelectedAdvisorForAssociation] = useState<Advisor | null>(null);
  const [isDetailDialogOpen, setIsDetailDialogOpen] = useState(false);
  const [selectedAdvisor, setSelectedAdvisor] = useState<Advisor | null>(null);
  const [formData, setFormData] = useState({
    email: '',
    given_name: '',
    family_name: '',
  });
  const { toast } = useToast();
  
  const dispatch = useAppDispatch();
  const { firm, advisors, clients: firmClients, isLoading, error } = useAppSelector((state) => state.firm);

  useEffect(() => {
    // If firm already exists in state (e.g., from fetchFirmById for superadmin), use it
    if (firm) {
      dispatch(fetchFirmAdvisors(firm.id));
      // Fetch firm clients if not already loaded
      if (firmClients.length === 0) {
        dispatch(fetchFirmClients());
      }
    } else {
      // Otherwise, fetch firm first to get firm ID (for firm_admin)
      dispatch(fetchFirm()).then((result) => {
        if (fetchFirm.fulfilled.match(result) && result.payload) {
          dispatch(fetchFirmAdvisors(result.payload.firm.id));
          dispatch(fetchFirmClients());
        }
      });
    }
  }, [dispatch, firm, firmClients.length]);

  // Filter advisors for overview:
  // - For firm advisors (with firm_id matching current firm): only show firm_advisor role
  // - For non-firm advisors (without firm_id or different firm_id): only show advisor role
  // - Exclude firm_admin and admin roles in all cases
  const advisorsWithoutAdmins = advisors.filter((advisor) => {
    const role = advisor.role as string;
    
    // Exclude firm_admin and admin roles
    if (role === 'firm_admin' || role === 'admin') {
      return false;
    }
    
    // For advisors belonging to the current firm, only show firm_advisor
    if (firm && advisor.firm_id === firm.id) {
      return role === 'firm_advisor';
    }
    
    // For non-firm advisors, only show advisor role
    return role === 'advisor';
  });

  const filteredAdvisors = advisorsWithoutAdmins.filter((advisor) => {
    const matchesSearch = 
      advisor.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      advisor.email.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const handleAddAdvisor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!firm) {
      toast({
        title: 'Error',
        description: 'Firm not found',
        variant: 'destructive',
      });
      return;
    }

    setIsSubmitting(true);

    try {
      await dispatch(addAdvisorToFirm({
        firmId: firm.id,
        advisorData: {
          email: formData.email,
          name: `${formData.given_name} ${formData.family_name}`.trim(),
        },
      })).unwrap();

      toast({
        title: 'Success',
        description: 'Advisor added successfully',
      });

      // Reset form and close dialog
      setFormData({ email: '', given_name: '', family_name: '' });
      setIsAddDialogOpen(false);
      
      // Refresh advisors list
      dispatch(fetchFirmAdvisors(firm.id));
    } catch (error: any) {
      // Extract error message from various possible formats
      let errorMessage = 'Failed to add advisor';
      if (typeof error === 'string') {
        errorMessage = error;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      } else if (error?.message) {
        errorMessage = error.message;
      } else if (error?.detail) {
        errorMessage = error.detail;
      } else if (error?.payload) {
        errorMessage = typeof error.payload === 'string' ? error.payload : error.payload?.detail || errorMessage;
      }

      toast({
        title: 'Error',
        description: errorMessage,
        variant: 'destructive',
      });

      setFormData({ email: '', given_name: '', family_name: '' });
      setIsAddDialogOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteClick = (advisorId: string) => {
    setAdvisorToDelete(advisorId);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!firm || !advisorToDelete) return;

    try {
      await dispatch(removeAdvisorFromFirm({
        firmId: firm.id,
        advisorId: advisorToDelete,
      })).unwrap();

      toast({
        title: 'Success',
        description: 'Advisor removed successfully',
      });

      setDeleteDialogOpen(false);
      setAdvisorToDelete(null);
      
      // Refresh advisors list
      dispatch(fetchFirmAdvisors(firm.id));
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to remove advisor',
        variant: 'destructive',
      });
    }
  };

  const handleSuspendClick = async (advisorId: string) => {
    if (!firm) return;

    setAdvisorToSuspend(advisorId);
    setIsLoadingEngagements(true);
    setReassignments({});

    try {
      const result = await dispatch(getAdvisorEngagements({
        firmId: firm.id,
        advisorId: advisorId,
      })).unwrap();

      setAdvisorEngagements(result);
      setSuspendDialogOpen(true);
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to fetch advisor engagements',
        variant: 'destructive',
      });
    } finally {
      setIsLoadingEngagements(false);
    }
  };

  const handleSuspendConfirm = async () => {
    if (!firm || !advisorToSuspend) return;

    // Check if there are primary engagements without reassignments
    if (advisorEngagements?.primary && advisorEngagements.primary.length > 0) {
      const missingReassignments = advisorEngagements.primary.filter(
        eng => !reassignments[eng.id]
      );

      if (missingReassignments.length > 0) {
        toast({
          title: 'Error',
          description: `Please assign a new advisor for all ${missingReassignments.length} primary engagement(s)`,
          variant: 'destructive',
        });
        return;
      }
    }

    // Check if there are any active advisors left (excluding the one being suspended)
    const activeAdvisorsAfterSuspend = advisorsWithoutAdmins.filter(
      a => a.is_active && a.id !== advisorToSuspend
    );

    if (activeAdvisorsAfterSuspend.length === 0) {
      toast({
        title: 'Error',
        description: 'Cannot suspend advisor: No active advisors will remain in the firm',
        variant: 'destructive',
      });
      return;
    }

    setIsSubmitting(true);

    try {
      await dispatch(suspendAdvisor({
        firmId: firm.id,
        advisorId: advisorToSuspend,
        reassignments: Object.keys(reassignments).length > 0 ? reassignments : undefined,
      })).unwrap();

      toast({
        title: 'Success',
        description: 'Advisor suspended successfully',
      });

      setSuspendDialogOpen(false);
      setAdvisorToSuspend(null);
      setAdvisorEngagements(null);
      setReassignments({});
      
      // Refresh advisors list
      dispatch(fetchFirmAdvisors(firm.id));
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to suspend advisor',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReactivate = async (advisorId: string) => {
    if (!firm) return;

    setIsSubmitting(true);

    try {
      await dispatch(reactivateAdvisor({
        firmId: firm.id,
        advisorId: advisorId,
      })).unwrap();

      toast({
        title: 'Success',
        description: 'Advisor reactivated successfully',
      });

      // Refresh advisors list
      dispatch(fetchFirmAdvisors(firm.id));
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to reactivate advisor',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAssociateClients = (advisorId: string) => {
    const advisor = advisorsWithoutAdmins.find((a) => a.id === advisorId);
    if (advisor) {
      setSelectedAdvisorForAssociation(advisor);
      setAssociateDialogOpen(true);
    }
  };

  const handleViewDetails = (advisorId: string) => {
    const advisor = advisorsWithoutAdmins.find((a) => a.id === advisorId);
    if (advisor) {
      setSelectedAdvisor(advisor);
      setIsDetailDialogOpen(true);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Advisors</h1>
          <p className="text-muted-foreground mt-1">Manage advisors in your firm</p>
        </div>
        <Dialog 
          open={isAddDialogOpen} 
          onOpenChange={(open) => {
            setIsAddDialogOpen(open);
            // Reset form when dialog closes
            if (!open) {
              setFormData({ email: '', given_name: '', family_name: '' });
            }
          }}
        >
          <DialogTrigger asChild>
            <Button className="btn-primary">
              <Plus className="w-4 h-4 mr-2" />
              Add Advisor
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New Advisor</DialogTitle>
              <DialogDescription>
                Add a new advisor to your firm. They will be able to manage client engagements.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleAddAdvisor} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email *</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="advisor@example.com"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="given_name">First Name</Label>
                  <Input
                    id="given_name"
                    value={formData.given_name}
                    onChange={(e) => setFormData({ ...formData, given_name: e.target.value })}
                    placeholder="Jane"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="family_name">Last Name</Label>
                  <Input
                    id="family_name"
                    value={formData.family_name}
                    onChange={(e) => setFormData({ ...formData, family_name: e.target.value })}
                    placeholder="Smith"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsAddDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? 'Adding...' : 'Add Advisor'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {firm && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="stat-card">
            <p className="text-sm text-muted-foreground">Total Advisors</p>
            <p className="text-2xl font-heading font-bold mt-1">
              {advisorsWithoutAdmins.length}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Firm Advisors only
            </p>
          </div>
          <div className="stat-card">
            <p className="text-sm text-muted-foreground">Active Advisors</p>
            <p className="text-2xl font-heading font-bold mt-1">
              {advisorsWithoutAdmins.filter((a) => a.is_active).length}
            </p>
          </div>
          <div className="stat-card">
            <p className="text-sm text-muted-foreground">Seats Used</p>
            <p className="text-2xl font-heading font-bold mt-1">
              {firm.seats_used ?? 0} / {firm?.seat_count ?? 0}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {firm.seat_count - firm.seats_used} available
            </p>
          </div>
        </div>
      )}

      <div className="card-trinity p-6">
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search advisors..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-trinity pl-10 w-full"
            />
          </div>
        </div>

        <AdvisorList
          advisors={advisorsWithoutAdmins}
          filteredAdvisors={filteredAdvisors}
          isLoading={isLoading}
          onSuspend={handleSuspendClick}
          onReactivate={handleReactivate}
          onDelete={handleDeleteClick}
          onViewDetails={handleViewDetails}
          onAssociateClients={handleAssociateClients}
        />
      </div>

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Advisor</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove this advisor from your firm? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm} className="bg-destructive text-destructive-foreground">
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Advisor Detail Dialog */}
      <Dialog
        open={isDetailDialogOpen}
        onOpenChange={(open) => {
          setIsDetailDialogOpen(open);
          if (!open) {
            setSelectedAdvisor(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Advisor Details</DialogTitle>
            <DialogDescription>
              View detailed information about the advisor
            </DialogDescription>
          </DialogHeader>
          {selectedAdvisor && (
            <div className="space-y-4 mt-4">
              <div className="flex items-center gap-3 pb-4 border-b">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <User className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg">
                    {selectedAdvisor.name || 'Unknown'}
                  </h3>
                  <p className="text-sm text-muted-foreground capitalize">
                    {selectedAdvisor.role.replace('_', ' ')}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Status</Label>
                  <span
                    className={cn(
                      'status-badge text-xs',
                      selectedAdvisor.is_active ? 'status-success' : 'status-warning'
                    )}
                  >
                    {selectedAdvisor.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Email</Label>
                  <div className="flex items-center gap-2">
                    <Mail className="w-4 h-4 text-muted-foreground" />
                    <p className="text-sm font-medium">{selectedAdvisor.email}</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Suspend Advisor Dialog */}
      <Dialog open={suspendDialogOpen} onOpenChange={setSuspendDialogOpen}>
        <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-warning" />
              Suspend Advisor
            </DialogTitle>
            <DialogDescription>
              {advisorEngagements && (advisorEngagements.primary.length > 0 || advisorEngagements.secondary.length > 0) ? (
                "This advisor is involved in engagements. Please assign new advisors to primary engagements before suspending."
              ) : (
                "You are about to suspend this advisor. They will lose access to all firm engagements."
              )}
            </DialogDescription>
          </DialogHeader>

          {isLoadingEngagements ? (
            <div className="py-8 text-center text-muted-foreground">Loading engagements...</div>
          ) : advisorEngagements && (advisorEngagements.primary.length > 0 || advisorEngagements.secondary.length > 0) ? (
            <div className="space-y-6">
              {/* Primary Engagements - Require Reassignment */}
              {advisorEngagements.primary.length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-warning" />
                    <h3 className="font-semibold">Primary Advisor Engagements ({advisorEngagements.primary.length})</h3>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    These engagements require a new primary advisor assignment:
                  </p>
                  <div className="space-y-3">
                    {advisorEngagements.primary.map((engagement) => {
                      const activeAdvisors = advisorsWithoutAdmins.filter(
                        a => a.is_active && a.id !== advisorToSuspend
                      );

                      return (
                        <div key={engagement.id} className="p-4 border border-border rounded-lg space-y-2">
                          <div className="flex items-start justify-between">
                            <div>
                              <p className="font-medium">{engagement.engagement_name}</p>
                              <p className="text-sm text-muted-foreground">
                                Client: {engagement.client_name || 'Unknown'}
                              </p>
                            </div>
                            <span className={cn(
                              "status-badge text-xs",
                              engagement.status === 'active' && "status-success"
                            )}>
                              {engagement.status}
                            </span>
                          </div>
                          <div className="space-y-2">
                            <Label className="text-sm">Assign New Primary Advisor *</Label>
                            <Select
                              value={reassignments[engagement.id] || ''}
                              onValueChange={(value) => {
                                setReassignments(prev => ({
                                  ...prev,
                                  [engagement.id]: value
                                }));
                              }}
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="Select advisor" />
                              </SelectTrigger>
                              <SelectContent>
                                {activeAdvisors.length === 0 ? (
                                  <SelectItem value="none" disabled>
                                    No active advisors available
                                  </SelectItem>
                                ) : (
                                  activeAdvisors.map((advisor) => (
                                    <SelectItem key={advisor.id} value={advisor.id}>
                                      {advisor.name || advisor.email}
                                    </SelectItem>
                                  ))
                                )}
                              </SelectContent>
                            </Select>
                            {activeAdvisors.length === 0 && (
                              <p className="text-xs text-destructive">
                                Cannot suspend: No active advisors available to reassign
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Secondary Engagements - Info Only */}
              {advisorEngagements.secondary.length > 0 && (
                <div className="space-y-4">
                  <h3 className="font-semibold">Secondary Advisor Engagements ({advisorEngagements.secondary.length})</h3>
                  <p className="text-sm text-muted-foreground">
                    These engagements will automatically remove this advisor from secondary advisor list:
                  </p>
                  <div className="space-y-2">
                    {advisorEngagements.secondary.map((engagement) => (
                      <div key={engagement.id} className="p-3 border border-border rounded-lg">
                        <p className="font-medium text-sm">{engagement.engagement_name}</p>
                        <p className="text-xs text-muted-foreground">
                          Client: {engagement.client_name} • Primary: {engagement.primary_advisor_name}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Warning if no active advisors after suspend */}
              {advisorsWithoutAdmins.filter(a => a.is_active && a.id !== advisorToSuspend).length === 0 && (
                <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-5 h-5 text-destructive mt-0.5" />
                    <div>
                      <p className="font-medium text-destructive">Cannot Suspend</p>
                      <p className="text-sm text-destructive/80 mt-1">
                        Suspending this advisor would leave no active advisors in the firm. Please add more advisors first.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : advisorEngagements && advisorEngagements.primary.length === 0 && advisorEngagements.secondary.length === 0 ? (
            <div className="space-y-4">
              <div className="p-4 bg-warning/10 border border-warning/20 rounded-lg">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-5 h-5 text-warning mt-0.5" />
                  <div>
                    <p className="font-medium text-warning">Warning</p>
                    <p className="text-sm text-warning/80 mt-1">
                      You are about to suspend this advisor. They will lose access to all firm resources.
                    </p>
                  </div>
                </div>
              </div>

              {/* Warning if no active advisors after suspend */}
              {advisorsWithoutAdmins.filter(a => a.is_active && a.id !== advisorToSuspend).length === 0 && (
                <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-5 h-5 text-destructive mt-0.5" />
                    <div>
                      <p className="font-medium text-destructive">Cannot Suspend</p>
                      <p className="text-sm text-destructive/80 mt-1">
                        Suspending this advisor would leave no active advisors in the firm. Please add more advisors first.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : null}

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button
              variant="outline"
              onClick={() => {
                setSuspendDialogOpen(false);
                setAdvisorToSuspend(null);
                setAdvisorEngagements(null);
                setReassignments({});
              }}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSuspendConfirm}
              disabled={
                isSubmitting ||
                (advisorEngagements?.primary && advisorEngagements.primary.length > 0 && 
                 Object.keys(reassignments).length !== advisorEngagements.primary.length) ||
                advisorsWithoutAdmins.filter(a => a.is_active && a.id !== advisorToSuspend).length === 0
              }
              className="bg-warning text-warning-foreground hover:bg-warning/90"
            >
              {isSubmitting ? 'Suspending...' : 'Suspend Advisor'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Associate Clients Dialog */}
      {selectedAdvisorForAssociation && (
        <AdvisorClientDialog
          open={associateDialogOpen}
          onOpenChange={(open) => {
            setAssociateDialogOpen(open);
            if (!open) {
              setSelectedAdvisorForAssociation(null);
            }
          }}
          advisor={{
            id: selectedAdvisorForAssociation.id,
            name: selectedAdvisorForAssociation.name,
            email: selectedAdvisorForAssociation.email,
            role: selectedAdvisorForAssociation.role,
            is_active: selectedAdvisorForAssociation.is_active,
            email_verified: false,
            created_at: selectedAdvisorForAssociation.created_at,
            firm_id: selectedAdvisorForAssociation.firm_id,
          }}
          firmClients={firmClients}
        />
      )}
    </div>
  );
}

