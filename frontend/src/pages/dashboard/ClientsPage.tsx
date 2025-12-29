import { useState, useEffect, useMemo } from 'react';
import { Search, MoreHorizontal, Building2, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface ClientFromEngagements {
  id: string;
  name: string;
  industry: string;
  status: 'Active' | 'Pending';
  engagements: number;
}

export default function ClientsPage() {
  const dispatch = useAppDispatch();
  const { engagements, isLoading, error } = useAppSelector((state) => state.engagement);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [industryFilter, setIndustryFilter] = useState('all');

  // Fetch engagements on mount
  useEffect(() => {
    dispatch(fetchEngagements(undefined));
  }, [dispatch]);

  // Extract unique clients from engagements
  const clientsFromEngagements = useMemo<ClientFromEngagements[]>(() => {
    const clientMap = new Map<string, {
      id: string;
      name: string;
      industries: Set<string>;
      engagementStatuses: Set<string>;
      engagementCount: number;
    }>();

    engagements.forEach(engagement => {
      const clientId = engagement.clientId;
      if (!clientMap.has(clientId)) {
        clientMap.set(clientId, {
          id: clientId,
          name: engagement.clientName,
          industries: new Set(),
          engagementStatuses: new Set(),
          engagementCount: 0,
        });
      }

      const client = clientMap.get(clientId)!;
      if (engagement.industryName) {
        client.industries.add(engagement.industryName);
      }
      client.engagementStatuses.add(engagement.status);
      client.engagementCount += 1;
    });

    // Convert to array and determine status
    return Array.from(clientMap.values()).map(client => {
      // Determine client status: Active if any engagement is active/draft, otherwise Pending/Inactive
      const hasActiveEngagement = Array.from(client.engagementStatuses).some(
        status => status === 'active' || status === 'draft'
      );
      const status: 'Active' | 'Pending' = hasActiveEngagement ? 'Active' : 'Pending';
      
      // Use the first industry found (or empty string if none)
      const industry = client.industries.size > 0 ? Array.from(client.industries)[0] : '';

      return {
        id: client.id,
        name: client.name,
        industry,
        status,
        engagements: client.engagementCount,
      };
    });
  }, [engagements]);

  const industries = useMemo(() => {
    const uniqueIndustries = new Set(clientsFromEngagements.map(c => c.industry).filter(Boolean));
    return ['all', ...Array.from(uniqueIndustries)];
  }, [clientsFromEngagements]);

  const filteredClients = clientsFromEngagements.filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesIndustry = industryFilter === 'all' || c.industry === industryFilter;
    return matchesSearch && matchesIndustry;
  });

  const activeClientsCount = clientsFromEngagements.filter(c => c.status === 'Active').length;

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
          <p className="text-sm text-muted-foreground">Active Clients</p>
          <p className="text-2xl font-heading font-bold mt-1">{activeClientsCount}</p>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
          <span className="ml-2 text-muted-foreground">Loading clients...</span>
        </div>
      )}

      {error && !isLoading && (
        <div className="text-center py-12">
          <p className="text-destructive mb-2">Error loading clients</p>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      )}

      {!isLoading && !error && (
        <div className="card-trinity p-6">
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="relative flex-1">
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
                      <div>
                        <h3 className="font-semibold text-foreground group-hover:text-accent transition-colors">{client.name}</h3>
                        {client.industry && (
                          <p className="text-sm text-muted-foreground">{client.industry}</p>
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
                        <DropdownMenuItem className="cursor-pointer">View Details</DropdownMenuItem>
                        <DropdownMenuItem className="cursor-pointer">New Engagement</DropdownMenuItem>
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
                    </div>
                    <span className="text-sm text-muted-foreground">{client.engagements} {client.engagements === 1 ? 'engagement' : 'engagements'}</span>
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
