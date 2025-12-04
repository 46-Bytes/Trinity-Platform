import { useState } from 'react';
import { Search, Plus, MoreHorizontal, Building2, Mail, Phone, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const mockClients = [
  { id: '1', name: 'Acme Corporation', contact: 'John Smith', email: 'john@acme.com', phone: '+61 400 000 001', industry: 'Manufacturing', status: 'Active', engagements: 3 },
  { id: '2', name: 'TechStart Inc', contact: 'Sarah Johnson', email: 'sarah@techstart.com', phone: '+61 400 000 002', industry: 'Technology', status: 'Active', engagements: 2 },
  { id: '3', name: 'Global Solutions', contact: 'Michael Brown', email: 'michael@globalsol.com', phone: '+61 400 000 003', industry: 'Consulting', status: 'Active', engagements: 4 },
  { id: '4', name: 'Innovate Ltd', contact: 'Emma Wilson', email: 'emma@innovate.com', phone: '+61 400 000 004', industry: 'Finance', status: 'Pending', engagements: 1 },
  { id: '5', name: 'Pacific Traders', contact: 'David Chen', email: 'david@pacific.com', phone: '+61 400 000 005', industry: 'Retail', status: 'Active', engagements: 2 },
];

export default function ClientsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [industryFilter, setIndustryFilter] = useState('all');

  const industries = ['all', ...new Set(mockClients.map(c => c.industry))];

  const filteredClients = mockClients.filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.contact.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesIndustry = industryFilter === 'all' || c.industry === industryFilter;
    return matchesSearch && matchesIndustry;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Clients</h1>
          <p className="text-muted-foreground mt-1">Manage your client relationships</p>
        </div>
        <button className="btn-primary">
          <Plus className="w-4 h-4" />
          Add Client
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="stat-card">
          <p className="text-sm text-muted-foreground">Total Clients</p>
          <p className="text-2xl font-heading font-bold mt-1">{mockClients.length}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm text-muted-foreground">Active Clients</p>
          <p className="text-2xl font-heading font-bold mt-1">{mockClients.filter(c => c.status === 'Active').length}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm text-muted-foreground">Total Engagements</p>
          <p className="text-2xl font-heading font-bold mt-1">{mockClients.reduce((sum, c) => sum + c.engagements, 0)}</p>
        </div>
      </div>

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
        </div>

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
                    <p className="text-sm text-muted-foreground">{client.industry}</p>
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
                    <DropdownMenuItem className="cursor-pointer">Edit Client</DropdownMenuItem>
                    <DropdownMenuItem className="cursor-pointer">New Engagement</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <span className="font-medium text-foreground">{client.contact}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Mail className="w-4 h-4" />
                  <span>{client.email}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Phone className="w-4 h-4" />
                  <span>{client.phone}</span>
                </div>
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
                <span className="text-sm text-muted-foreground">{client.engagements} engagements</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
