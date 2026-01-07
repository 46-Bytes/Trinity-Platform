import { useState, useEffect, useMemo, useCallback } from 'react';
import { Search, MoreHorizontal, Building2, Loader2, Eye, FileText, Plus, Mail, Phone } from 'lucide-react';
import { cn, getUniqueClientIds } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import { fetchFirmClients, addClientToFirm, fetchFirm } from '@/store/slices/firmReducer';
import { fetchClientUsers } from '@/store/slices/clientReducer';
import { useAuth } from '@/context/AuthContext';
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
  const { firm, clients: firmClients, isLoading: firmClientsLoading, error: firmError } = useAppSelector((state) => state.firm);
  const { clients: adminClients, isLoading: adminClientsLoading, error: adminClientsError } = useAppSelector((state) => state.client);
  const { toast } = useToast();
  
  const [searchQuery, setSearchQuery] = useState('');
  const [clients, setClients] = useState<Client[]>([]);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    name: '',
    first_name: '',
    last_name: '',
  });

  // Check if user is advisor (including firm_advisor)
  const isAdvisor = user?.role === 'advisor' || user?.role === 'firm_advisor';
  // Check if user is admin (can access users API)
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  // Check if user is firm admin
  const isFirmAdmin = user?.role === 'firm_admin';

  const fetchClients = useCallback(async () => {
    // For firm admin, use firm reducer clients
    if (isFirmAdmin) {
      dispatch(fetchFirmClients());
      return;
    }

    // For advisors, load clients from advisor-client associations API
    if (isAdvisor) {
      try {
        const token = localStorage.getItem('auth_token');
        if (!token) {
          setClients([]);
          return;
        }

        const response = await fetch(
          `${API_BASE_URL}/api/advisor-client?status_filter=active`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          },
        );

        if (!response.ok) {
          console.error('Failed to fetch advisor clients');
          setClients([]);
          return;
        }

        const associations = await response.json();

        // Map advisor-client associations to the Client shape used in this page
        const advisorClients: Client[] = associations.map((assoc: any) => ({
          id: assoc.client_id,
          name: assoc.client_name || assoc.client_email || 'Unknown Client',
          email: assoc.client_email || '',
          industry: '',
          status: 'Active',
          engagements: 0, // Will be updated from engagements data below
          is_active: true,
          email_verified: false,
          role: 'client',
        }));

        setClients(advisorClients);
      } catch (error) {
        console.error('Error fetching advisor clients:', error);
        setClients([]);
      }
      return;
    }

    // For admins, load from client reducer
    if (!isAdmin) {
      setClients([]);
      return;
    }

    // Data will come from client reducer via adminClients selector
    dispatch(fetchClientUsers());
  }, [isAdvisor, isAdmin, isFirmAdmin, dispatch]);

  // Fetch firm for firm admin
  useEffect(() => {
    if (user && isFirmAdmin && !firm) {
      dispatch(fetchFirm());
    }
  }, [dispatch, user, isFirmAdmin, firm]);

  // Fetch engagements on mount
  useEffect(() => {
    if (user && !isFirmAdmin) {
      dispatch(fetchEngagements(undefined));
    }
  }, [dispatch, user, isFirmAdmin]);

  // Fetch clients when engagements are loaded (especially important for advisors)
  useEffect(() => {
    if (user && !engagementsLoading && !isFirmAdmin) {
      fetchClients();
    }
  }, [user, engagementsLoading, fetchClients, engagements.length, isFirmAdmin]);

  // Choose base clients by role
  const baseClients: Client[] = useMemo(() => {
    if (isFirmAdmin) {
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

    if (isAdmin) {
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

    return clients;
  }, [isFirmAdmin, isAdmin, firmClients, adminClients, clients]);

  // Merge client data with engagement data
  const clientsWithEngagements = useMemo<Client[]>(() => {
    // For firm admin and admins, return base clients as-is (no engagement enrichment needed)
    if (isFirmAdmin || isAdmin) {
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
  }, [baseClients, engagements, isFirmAdmin, isAdmin]);


  const filteredClients = clientsWithEngagements.filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.email.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch
  });

  const activeClientsCount = clientsWithEngagements.filter(c => c.status === 'Active').length;
  const totalClientsCount = clientsWithEngagements.length;

  const isLoadingData =
    engagementsLoading ||
    (isFirmAdmin && firmClientsLoading) ||
    (isAdmin && adminClientsLoading);

  const error = isFirmAdmin ? firmError : isAdmin ? adminClientsError : null;

  const handleAddClient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user || !isFirmAdmin) {
      toast({
        title: 'Error',
        description: 'Only firm admins can add clients',
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
        name: formData.name || undefined,
        first_name: formData.first_name || undefined,
        last_name: formData.last_name || undefined,
      }));

      if (addClientToFirm.fulfilled.match(result)) {
        toast({
          title: 'Success',
          description: 'Client added successfully',
        });
        setIsAddDialogOpen(false);
        setFormData({ email: '', name: '', first_name: '', last_name: '' });
        // Refresh clients list
        dispatch(fetchFirmClients());
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
        {isFirmAdmin && (
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
                  Add a new client to your firm.
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
                <div className="space-y-2">
                  <Label htmlFor="name">Full Name</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="John Doe"
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
                        <DropdownMenuItem className="cursor-pointer">
                          <Eye className="w-4 h-4 mr-2" />
                          View Details
                        </DropdownMenuItem>
                        <DropdownMenuItem className="cursor-pointer">
                          <FileText className="w-4 h-4 mr-2" />
                          New Engagement
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
    </div>
  );
}
