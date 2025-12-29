import { useState, useEffect, useMemo } from 'react';
import { Search, MoreHorizontal, Building2, Loader2, Eye, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

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
}

export default function ClientsPage() {
  const dispatch = useAppDispatch();
  const { engagements, isLoading: engagementsLoading } = useAppSelector((state) => state.engagement);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);

  // Fetch engagements and clients on mount
  useEffect(() => {
    dispatch(fetchEngagements(undefined));
    fetchClients();
  }, [dispatch]);

  const fetchClients = async () => {
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
      }
    } catch (error) {
      console.error('Error fetching clients:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Merge client data with engagement data
  const clientsWithEngagements = useMemo<Client[]>(() => {
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
    return clients.map(client => {
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
  }, [clients, engagements]);

  const filteredClients = clientsWithEngagements.filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.email.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const activeClientsCount = clientsWithEngagements.filter(c => c.status === 'Active').length;
  const totalClientsCount = clientsWithEngagements.length;

  const isLoadingData = isLoading || engagementsLoading;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Clients</h1>
          <p className="text-muted-foreground mt-1">Manage your client relationships</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="stat-card">
          <p className="text-sm text-muted-foreground">Total Clients</p>
          <p className="text-2xl font-heading font-bold mt-1">{totalClientsCount}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm text-muted-foreground">Active Clients</p>
          <p className="text-2xl font-heading font-bold mt-1">{activeClientsCount}</p>
        </div>
      </div>

      {isLoadingData && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
          <span className="ml-2 text-muted-foreground">Loading clients...</span>
        </div>
      )}

      {!isLoadingData && (
        <div className="card-trinity p-6">
          <div className="mb-6">
            <div className="relative max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search clients..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-trinity pl-10 w-full"
              />
            </div>
          </div>

          {filteredClients.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-muted-foreground">No clients found</p>
              {searchQuery && (
                <p className="text-sm text-muted-foreground mt-2">
                  Try adjusting your search
                </p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredClients.map((client) => (
                <div key={client.id} className="card-trinity p-5 hover:shadow-trinity-md cursor-pointer group">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                        <Building2 className="w-6 h-6 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-foreground group-hover:text-accent transition-colors truncate">
                          {client.name}
                        </h3>
                        <p className="text-sm text-muted-foreground truncate">{client.email}</p>
                        {client.industry && (
                          <p className="text-sm text-muted-foreground mt-1">{client.industry}</p>
                        )}
                      </div>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="p-1.5 rounded-lg hover:bg-muted transition-colors opacity-0 group-hover:opacity-100">
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

                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "status-badge",
                        client.status === 'Active' ? "status-success" : "status-warning"
                      )}>
                        {client.status}
                      </span>
                      {!client.email_verified && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-800">
                          Unverified
                        </span>
                      )}
                    </div>
                    <span className="text-sm text-muted-foreground">
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
