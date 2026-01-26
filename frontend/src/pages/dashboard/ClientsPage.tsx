import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Search, MoreHorizontal, Building2, Loader2, Eye, Plus, Mail, Phone } from 'lucide-react';
import { cn, getUniqueClientIds } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import { fetchFirmClients, addClientToFirm, fetchFirm, fetchFirmAdvisors, fetchFirmClientsById } from '@/store/slices/firmReducer';
import { fetchClientUsers } from '@/store/slices/clientReducer';
import { useAuth } from '@/context/AuthContext';
import {
  fetchAdvisorClientsFromAssociations,
  getClientFetchingStrategy,
  type Client as ClientType,
} from '@/lib/clientFetcher';
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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Client {
  id: string;
  name: string;
  email: string;
  industry: string;
  status: 'Active' | 'Pending';
  engagements: number;
  is_active: boolean;
  email_verified: boolean;
  role?: string;
  contact?: string;
  phone?: string;
}

export default function ClientsPage() {
  const dispatch = useAppDispatch();
  const { user } = useAuth();
  const { engagements, isLoading: engagementsLoading } = useAppSelector((state) => state.engagement);
  const { firm, clients: firmClients, advisors, isLoading: firmClientsLoading, error: firmError } = useAppSelector((state) => state.firm);
  const { clients: adminClients, isLoading: adminClientsLoading, error: adminClientsError } = useAppSelector((state) => state.client);
  const { toast } = useToast();
  
  const [searchQuery, setSearchQuery] = useState('');
  const [clients, setClients] = useState<Client[]>([]);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isDetailDialogOpen, setIsDetailDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    primary_advisor_id: '',
  });

  // Get client fetching strategy based on user role - memoize to prevent infinite loops
  const strategy = useMemo(() => getClientFetchingStrategy(user), [user?.role]);
  
  // Extract individual boolean values to use as stable dependencies
  // For superadmin viewing a firm, use firm clients if firm exists in state
  const isSuperAdminViewingFirm = user?.role === 'super_admin' && firm !== null;
  const shouldUseFirmClients = strategy.shouldUseFirmClients || isSuperAdminViewingFirm;
  const shouldUseEngagements = strategy.shouldUseEngagements && !isSuperAdminViewingFirm;
  const shouldUseAssociations = strategy.shouldUseAssociations && !isSuperAdminViewingFirm;
  const shouldUseAdminClients = strategy.shouldUseAdminClients && !isSuperAdminViewingFirm;

  const fetchClients = useCallback(async () => {
    // For firm admin or superadmin viewing a firm, use firm reducer clients
    if (shouldUseFirmClients) {
      // If superadmin is viewing a firm, clients should already be fetched by fetchFirmClientsById
      // Don't call fetchFirmClients() which would overwrite with wrong data
      if (isSuperAdminViewingFirm) {
        // Clients are already in state from fetchFirmClientsById, just return
        return;
      }
      // For firm admin, fetch their firm's clients
      dispatch(fetchFirmClients());
      return;
    }

    // For both regular advisor and firm_advisor, load clients from advisor-client associations API
    if (shouldUseAssociations) {
      try {
        const advisorClients = await fetchAdvisorClientsFromAssociations();
        setClients(advisorClients);
      } catch (error) {
        console.error('Error fetching advisor clients from associations:', error);
        setClients([]);
      }
      return;
    }

    // For admins, load from client reducer
    if (shouldUseAdminClients) {
      dispatch(fetchClientUsers());
      return;
    }

    setClients([]);
  }, [shouldUseFirmClients, shouldUseEngagements, shouldUseAssociations, shouldUseAdminClients, user?.id, dispatch, isSuperAdminViewingFirm]);

  // Fetch firm for firm admin (only if not already in state, e.g., from fetchFirmById for superadmin)
  useEffect(() => {
    if (user && shouldUseFirmClients && !firm) {
      dispatch(fetchFirm());
    }
  }, [dispatch, user?.id, shouldUseFirmClients, firm]);

  // Fetch firm advisors when dialog opens (for both firm_admin and superadmin viewing firm)
  useEffect(() => {
    if (isAddDialogOpen && firm && shouldUseFirmClients) {
      dispatch(fetchFirmAdvisors(firm.id));
    }
  }, [isAddDialogOpen, firm, shouldUseFirmClients, dispatch]);

  // Fetch clients for firm admin (but not for superadmin viewing a firm - those are fetched by FirmDetailsClients)
  useEffect(() => {
    if (user && shouldUseFirmClients && !isSuperAdminViewingFirm) {
      fetchClients();
    }
  }, [user?.id, shouldUseFirmClients, isSuperAdminViewingFirm, fetchClients]);

  // Fetch engagements on mount (needed for regular advisor, not for firm_advisor anymore)
  useEffect(() => {
    if (user && shouldUseAssociations && user.role === 'advisor') {
      dispatch(fetchEngagements(undefined));
    }
  }, [dispatch, user?.id, user?.role, shouldUseAssociations]);

  // Track if we've already fetched clients to prevent infinite loops
  const hasFetchedClientsRef = useRef(false);
  
  useEffect(() => {
    if (user && shouldUseAssociations && !hasFetchedClientsRef.current) {
      hasFetchedClientsRef.current = true;
      fetchClients();
    }
    // Reset flag when user or strategy changes
    if (!shouldUseAssociations) {
      hasFetchedClientsRef.current = false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, shouldUseAssociations]);

  // Choose base clients by role
  const baseClients: Client[] = useMemo(() => {
    if (shouldUseFirmClients) {
      return firmClients.map(client => ({
        id: client.id,
        name: client.name || 'Unknown',
        email: client.email || '',
        industry: '',
        status: client.is_active ? 'Active' as const : 'Pending' as const,
        engagements: 0,
        is_active: client.is_active,
        email_verified: false,
        role: 'client',
      }));
    }

    if (strategy.shouldUseAdminClients) {
      return adminClients.map(client => ({
        id: client.id,
        name: client.name || 'Unknown',
        email: client.email || '',
        industry: '',
        status: client.is_active ? 'Active' as const : 'Pending' as const,
        engagements: 0,
        is_active: client.is_active,
        email_verified: client.email_verified ?? false,
        role: client.role || 'client',
      }));
    }

    // For firm_advisor and regular advisor, use clients from state
    return clients;
  }, [shouldUseFirmClients, strategy.shouldUseAdminClients, firmClients, adminClients, clients]);

  const clientsWithEngagements = useMemo<Client[]>(() => {
    if (shouldUseFirmClients || strategy.shouldUseAdminClients) {
      return baseClients;
    }

    // Create a map of client engagements
    const engagementMap = new Map<string, {
      industries: Set<string>;
      engagementStatuses: Set<string>;
      engagementCount: number;
    }>();

    engagements.forEach(engagement => {
      const clientId = engagement.clientId;
      if (!engagementMap.has(clientId)) {
        engagementMap.set(clientId, {
          industries: new Set(),
          engagementStatuses: new Set(),
          engagementCount: 0,
        });
      }

      const clientEngagements = engagementMap.get(clientId)!;
      if (engagement.industryName) {
        clientEngagements.industries.add(engagement.industryName);
      }
      clientEngagements.engagementStatuses.add(engagement.status);
      clientEngagements.engagementCount += 1;
    });

    // Merge client data with engagement data
    return baseClients.map(client => {
      const clientEngagements = engagementMap.get(client.id) || {
        industries: new Set<string>(),
        engagementStatuses: new Set<string>(),
        engagementCount: 0,
      };

      const hasActiveEngagement = Array.from(clientEngagements.engagementStatuses).some(
        status => status === 'active' || status === 'draft'
      );
      const status: 'Active' | 'Pending' = hasActiveEngagement || (client.is_active && clientEngagements.engagementCount === 0) 
        ? 'Active' 
        : 'Pending';
      
      const industry = clientEngagements.industries.size > 0 
        ? Array.from(clientEngagements.industries)[0] 
        : '';

      return {
        ...client,
        industry,
        status,
        engagements: clientEngagements.engagementCount,
      };
    });
  }, [baseClients, engagements, shouldUseFirmClients, strategy.shouldUseAdminClients]);


  const filteredClients = clientsWithEngagements.filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.email.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch
  });

  const activeClientsCount = clientsWithEngagements.filter(c => c.status === 'Active').length;
  const totalClientsCount = clientsWithEngagements.length;

  const isLoadingData =
    engagementsLoading ||
    (shouldUseFirmClients && firmClientsLoading) ||
    (strategy.shouldUseAdminClients && adminClientsLoading);

  const error = shouldUseFirmClients ? firmError : strategy.shouldUseAdminClients ? adminClientsError : null;

  const handleAddClient = async (e: React.FormEvent) => {
    e.preventDefault();
    // Allow firm_admin or superadmin viewing a firm to add clients
    if (!user || !shouldUseFirmClients) {
      toast({
        title: 'Error',
        description: 'Only firm admins and super admins can add clients',
        variant: 'destructive',
      });
      return;
    }

    // Get firm ID from firm state or user's firmId
    const firmId = firm?.id || user?.firmId;
    if (!firmId) {
      toast({
        title: 'Error',
        description: 'Firm ID not found. Please refresh the page.',
        variant: 'destructive',
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await dispatch(addClientToFirm({
        firmId,
        email: formData.email,
        first_name: formData.first_name || undefined,
        last_name: formData.last_name || undefined,
        primaryAdvisorId: formData.primary_advisor_id || undefined,
      }));

      if (addClientToFirm.fulfilled.match(result)) {
        toast({
          title: 'Success',
          description: 'Client added successfully',
        });
        setIsAddDialogOpen(false);
        setFormData({ email: '', first_name: '', last_name: '', primary_advisor_id: '' });
        // Refresh clients list - use appropriate fetch based on user role
        if (isSuperAdminViewingFirm) {
          dispatch(fetchFirmClientsById(firmId));
        } else {
          dispatch(fetchFirmClients());
        }
      } else {
        throw new Error(result.payload as string || 'Failed to add client');
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to add client',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 w-full min-w-0" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 w-full min-w-0">
        <div className="w-full min-w-0">
          <h1 className="font-heading text-xl sm:text-2xl font-bold text-foreground break-words">Clients</h1>
          <p className="text-muted-foreground mt-1 break-words">Manage your client relationships</p>
        </div>
        {shouldUseFirmClients && (
          <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
            <DialogTrigger asChild>
              <Button className="btn-primary">
                <Plus className="w-4 h-4 mr-2" />
                Add Client
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add New Client</DialogTitle>
                <DialogDescription>
                  Add a new client to firm.
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleAddClient} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email *</Label>
                  <Input
                    id="email"
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="client@example.com"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="first_name">First Name</Label>
                    <Input
                      id="first_name"
                      value={formData.first_name}
                      onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                      placeholder="John"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="last_name">Last Name</Label>
                    <Input
                      id="last_name"
                      value={formData.last_name}
                      onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                      placeholder="Doe"
                    />
                  </div>
                </div>
                {shouldUseFirmClients && (
                  <div className="space-y-2">
                    <Label htmlFor="primary_advisor">Primary Advisor (Optional)</Label>
                    <Select
                      value={formData.primary_advisor_id || undefined}
                      onValueChange={(value) => setFormData({ ...formData, primary_advisor_id: value === "none" ? "" : value })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select a primary advisor (optional)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">None</SelectItem>
                        {advisors
                          .filter((advisor) => 
                            advisor.role === 'firm_advisor' && 
                            advisor.firm_id === firm?.id &&
                            advisor.is_active
                          )
                          .map((advisor) => (
                            <SelectItem key={advisor.id} value={advisor.id}>
                              {advisor.name || advisor.email}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div className="flex justify-end gap-2 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsAddDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? 'Adding...' : 'Add Client'}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4 w-full min-w-0">
        <div className="stat-card w-full min-w-0" style={{ maxWidth: '100%' }}>
          <p className="text-sm text-muted-foreground break-words">Total Clients</p>
          <p className="text-xl sm:text-2xl font-heading font-bold mt-1 break-words">{totalClientsCount}</p>
        </div>
        <div className="stat-card w-full min-w-0" style={{ maxWidth: '100%' }}>
          <p className="text-sm text-muted-foreground break-words">Active Clients</p>
          <p className="text-xl sm:text-2xl font-heading font-bold mt-1 break-words">{activeClientsCount}</p>
        </div>
        <div className="stat-card w-full min-w-0" style={{ maxWidth: '100%' }}>
          <p className="text-sm text-muted-foreground break-words">Total Engagements</p>
          <p className="text-xl sm:text-2xl font-heading font-bold mt-1 break-words">
            {clientsWithEngagements.reduce((sum, c) => sum + c.engagements, 0)}
          </p>
        </div>
      </div>

      {error && (
        <div className="card-trinity p-4 bg-destructive/10 border border-destructive/20">
          <p className="text-destructive">{error}</p>
        </div>
      )}

      {isLoadingData && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
          <span className="ml-2 text-muted-foreground">Loading clients...</span>
        </div>
      )}

      {!isLoadingData && (
        <div className="card-trinity p-3 sm:p-4 md:p-6 w-full min-w-0" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
          <div className="mb-4 sm:mb-6 w-full min-w-0">
            <div className="relative w-full max-w-md mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search clients..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-trinity pl-10 w-full"
                style={{ maxWidth: '100%' }}
              />
            </div>
          </div>

          {filteredClients.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-muted-foreground break-words">No clients found</p>
              {searchQuery && (
                <p className="text-sm text-muted-foreground mt-2 break-words">
                  Try adjusting your search
                </p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 w-full min-w-0">
              {filteredClients.map((client) => (
                <div key={client.id} className="card-trinity p-3 sm:p-4 md:p-5 hover:shadow-trinity-md cursor-pointer group w-full min-w-0" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
                  <div className="flex items-start justify-between mb-3 sm:mb-4 gap-2 w-full min-w-0">
                    <div className="flex items-center gap-2 sm:gap-3 flex-1 min-w-0">
                      <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                        <Building2 className="w-5 h-5 sm:w-6 sm:h-6 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0 overflow-hidden">
                        <h3 className="font-semibold text-sm sm:text-base text-foreground group-hover:text-accent transition-colors truncate break-words" style={{ maxWidth: '100%' }}>
                          {client.name}
                        </h3>
                        <p className="text-xs sm:text-sm text-muted-foreground truncate break-words" style={{ maxWidth: '100%' }}>{client.email}</p>
                        {client.industry && (
                          <p className="text-xs sm:text-sm text-muted-foreground mt-1 break-words" style={{ maxWidth: '100%' }}>{client.industry}</p>
                        )}
                      </div>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="p-1.5 rounded-lg hover:bg-muted transition-colors opacity-0 group-hover:opacity-100 flex-shrink-0">
                          <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem 
                          className="cursor-pointer"
                          onClick={() => {
                            setSelectedClient(client);
                            setIsDetailDialogOpen(true);
                          }}
                        >
                          <Eye className="w-4 h-4 mr-2" />
                          View Details
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  <div className="flex items-center justify-between mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-border gap-2 flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={cn(
                        "status-badge text-xs",
                        client.status === 'Active' ? "status-success" : "status-warning"
                      )}>
                        {client.status}
                      </span>
                      {!client.email_verified && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-800 whitespace-nowrap">
                          Unverified
                        </span>
                      )}
                    </div>
                    <span className="text-xs sm:text-sm text-muted-foreground whitespace-nowrap">
                      {client.engagements} {client.engagements === 1 ? 'engagement' : 'engagements'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Client Detail Dialog */}
      <Dialog open={isDetailDialogOpen} onOpenChange={setIsDetailDialogOpen}>
        <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Client Details</DialogTitle>
            <DialogDescription>
              View detailed information about the client
            </DialogDescription>
          </DialogHeader>
          {selectedClient && (
            <div className="space-y-4 mt-4">
              <div className="flex items-center gap-3 pb-4 border-b">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <Building2 className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg">{selectedClient.name}</h3>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Status</Label>
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "status-badge text-xs",
                      selectedClient.status === 'Active' ? "status-success" : "status-warning"
                    )}>
                      {selectedClient.status}
                    </span>
                    {!selectedClient.email_verified && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-800">
                        Unverified
                      </span>
                    )}
                  </div>
                </div>

                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Engagements</Label>
                  <p className="text-sm font-medium">
                    {selectedClient.engagements} {selectedClient.engagements === 1 ? 'engagement' : 'engagements'}
                  </p>
                </div>

                {selectedClient.industry && (
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Industry</Label>
                    <p className="text-sm font-medium">{selectedClient.industry}</p>
                  </div>
                )}

                {selectedClient.phone && (
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Phone</Label>
                    <div className="flex items-center gap-2">
                      <Phone className="w-4 h-4 text-muted-foreground" />
                      <p className="text-sm font-medium">{selectedClient.phone}</p>
                    </div>
                  </div>
                )}

                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Email</Label>
                  <div className="flex items-center gap-2">
                    <Mail className="w-4 h-4 text-muted-foreground" />
                    <p className="text-sm font-medium">{selectedClient.email}</p>
                  </div>
                </div>

                {selectedClient.role && (
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Role</Label>
                    <p className="text-sm font-medium capitalize">{selectedClient.role}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
