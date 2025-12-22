import { useState, useEffect, useMemo, useCallback } from 'react';
import { Search, MoreHorizontal, Building2, Loader2, Eye, FileText, Plus, Mail, Phone } from 'lucide-react';
import { cn, getUniqueClientIds } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import { fetchFirmClients, addClientToFirm } from '@/store/slices/firmReducer';
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
  const { clients: firmClients, isLoading: firmClientsLoading, error: firmError } = useAppSelector((state) => state.firm);
  const { toast } = useToast();
  
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    name: '',
    given_name: '',
    family_name: '',
  });

  // Check if user is advisor (including firm_advisor)
  const isAdvisor = user?.role === 'advisor' || user?.role === 'firm_advisor';
  // Check if user is admin (can access users API)
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  // Check if user is firm admin
  const isFirmAdmin = user?.role === 'firm_admin';

  // Build clients from engagements for advisors
  const buildClientsFromEngagements = useCallback(() => {
    if (!isAdvisor || engagements.length === 0) {
      return [];
    }

    // Create a map of unique clients from engagements
    const clientMap = new Map<string, {
      id: string;
      name: string;
      email: string;
      engagements: number;
    }>();

    engagements.forEach(engagement => {
      const clientId = engagement.clientId;
      if (!clientMap.has(clientId)) {
        const clientName = engagement.clientName || 'Unknown Client';
        // Try to extract email from name, or create a reasonable default
        let email = clientName;
        if (!clientName.includes('@')) {
          // Create a placeholder email from the name
          email = `${clientName.toLowerCase().replace(/[^a-z0-9]/g, '.').replace(/\.+/g, '.').replace(/^\.|\.$/g, '')}@client.local`;
        }
        
        clientMap.set(clientId, {
          id: clientId,
          name: clientName,
          email: email,
          engagements: 0,
        });
      }
      const client = clientMap.get(clientId)!;
      client.engagements += 1;
    });

    return Array.from(clientMap.values()).map(client => ({
      id: client.id,
      name: client.name,
      email: client.email,
      industry: '', // Will be set in clientsWithEngagements
      status: 'Active' as const,
      engagements: client.engagements,
      is_active: true,
      email_verified: false,
      role: 'client',
    }));
  }, [isAdvisor, engagements]);

  const fetchClients = useCallback(async () => {
    // For firm admin, use firm reducer clients
    if (isFirmAdmin) {
      dispatch(fetchFirmClients());
      return;
    }

    // For advisors, build clients from engagements instead of calling API
    if (isAdvisor) {
      setIsLoading(true);
      try {
        const clientsFromEngagements = buildClientsFromEngagements();
        setClients(clientsFromEngagements);
      } catch (error) {
        console.error('Error building clients from engagements:', error);
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // For admins, fetch from API
    if (!isAdmin) {
      setClients([]);
      return;
    }

    setIsLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return;

      // Fetch all users with role='client'
      const response = await fetch(`${API_BASE_URL}/api/users?role=client`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const users = await response.json();
        // Filter out firm_admin and firm_advisor roles
        const filteredUsers = users.filter((user: any) => 
          user.role !== 'firm_admin' && user.role !== 'firm_advisor'
        );
        setClients(filteredUsers);
      } else {
        console.error('Failed to fetch clients');
        setClients([]);
      }
    } catch (error) {
      console.error('Error fetching clients:', error);
      setClients([]);
    } finally {
      setIsLoading(false);
    }
  }, [isAdvisor, isAdmin, isFirmAdmin, buildClientsFromEngagements, dispatch]);

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

  // For firm admin, use clients from firm reducer
  const clientsToUse = isFirmAdmin ? firmClients.map(client => ({
    id: client.id,
    name: client.name || 'Unknown',
    email: client.email || '',
    industry: '',
    status: client.is_active ? 'Active' as const : 'Pending' as const,
    engagements: 0,
    is_active: client.is_active,
    email_verified: false,
    role: 'client',
  })) : clients;

  // Merge client data with engagement data
  const clientsWithEngagements = useMemo<Client[]>(() => {
    // For firm admin, return clients as-is
    if (isFirmAdmin) {
      return clientsToUse;
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
    return clientsToUse.map(client => {
      const clientEngagements = engagementMap.get(client.id) || {
        industries: new Set<string>(),
        engagementStatuses: new Set<string>(),
        engagementCount: 0,
      };

      // Determine client status: Active if any engagement is active/draft, or if client is active with no engagements
      const hasActiveEngagement = Array.from(clientEngagements.engagementStatuses).some(
        status => status === 'active' || status === 'draft'
      );
      const status: 'Active' | 'Pending' = hasActiveEngagement || (client.is_active && clientEngagements.engagementCount === 0) 
        ? 'Active' 
        : 'Pending';
      
      // Use the first industry found (or empty string if none)
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
  }, [clientsToUse, engagements, isFirmAdmin]);

  const industries = ['all', ...new Set(clientsWithEngagements.map(c => c.industry).filter(Boolean))];
  const [industryFilter, setIndustryFilter] = useState('all');

  const filteredClients = clientsWithEngagements.filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesIndustry = industryFilter === 'all' || c.industry === industryFilter;
    return matchesSearch && matchesIndustry;
  });

  const activeClientsCount = clientsWithEngagements.filter(c => c.status === 'Active').length;
  const totalClientsCount = clientsWithEngagements.length;

  const isLoadingData = isLoading || engagementsLoading || (isFirmAdmin && firmClientsLoading);
  const error = isFirmAdmin ? firmError : null;

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

    setIsSubmitting(true);
    try {
      // For firm admin, we need to get the firm ID first
      // This would need to be implemented based on your API
      toast({
        title: 'Error',
        description: 'Add client functionality needs firm ID',
        variant: 'destructive',
      });
      setIsAddDialogOpen(false);
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
                    <Label htmlFor="given_name">First Name</Label>
                    <Input
                      id="given_name"
                      value={formData.given_name}
                      onChange={(e) => setFormData({ ...formData, given_name: e.target.value })}
                      placeholder="John"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="family_name">Last Name</Label>
                    <Input
                      id="family_name"
                      value={formData.family_name}
                      onChange={(e) => setFormData({ ...formData, family_name: e.target.value })}
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
            {industries.length > 1 && (
              <select 
                className="input-trinity w-full sm:w-48"
                value={industryFilter}
                onChange={(e) => setIndustryFilter(e.target.value)}
              >
                <option value="all">All Industries</option>
                {industries.filter(i => i !== 'all').map((industry) => (
                  <option key={industry} value={industry}>{industry}</option>
                ))}
              </select>
            )}
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
