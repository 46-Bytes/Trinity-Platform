import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { roleLabels, roleColors, UserRole } from '@/types/auth';
import { Search, Plus, MoreHorizontal, Filter, Mail, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const mockUsers = [
  { id: '1', name: 'Sarah Mitchell', email: 'sarah@trinity.com', role: 'super_admin' as UserRole, status: 'Active', lastActive: '2 min ago' },
  { id: '2', name: 'James Wilson', email: 'james@trinity.com', role: 'admin' as UserRole, status: 'Active', lastActive: '15 min ago' },
  { id: '3', name: 'Emma Thompson', email: 'emma@trinity.com', role: 'advisor' as UserRole, status: 'Active', lastActive: '1 hour ago' },
  { id: '4', name: 'Michael Chen', email: 'michael@company.com', role: 'client' as UserRole, status: 'Active', lastActive: '3 hours ago' },
  { id: '5', name: 'Lisa Anderson', email: 'lisa@firm.com', role: 'firm_advisor' as UserRole, status: 'Active', lastActive: '5 hours ago' },
  { id: '6', name: 'David Roberts', email: 'david@firm.com', role: 'firm_admin' as UserRole, status: 'Inactive', lastActive: '2 days ago' },
];

export default function UsersPage() {
  const { user } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<UserRole | 'all'>('all');

  const filteredUsers = mockUsers.filter(u => {
    const matchesSearch = u.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesRole = roleFilter === 'all' || u.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">User Management</h1>
          <p className="text-muted-foreground mt-1">Manage platform users and their roles</p>
        </div>
        <button className="btn-primary">
          <Plus className="w-4 h-4" />
          Add User
        </button>
      </div>

      <div className="card-trinity p-6">
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search users..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-trinity pl-10 w-full"
            />
          </div>
          <select 
            className="input-trinity w-full sm:w-48"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value as UserRole | 'all')}
          >
            <option value="all">All Roles</option>
            {Object.entries(roleLabels).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="table-trinity">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last Active</th>
                <th className="w-12"></th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-medium">
                        {u.name.charAt(0)}
                      </div>
                      <div>
                        <p className="font-medium">{u.name}</p>
                        <p className="text-sm text-muted-foreground">{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={cn("status-badge", roleColors[u.role])}>
                      {roleLabels[u.role]}
                    </span>
                  </td>
                  <td>
                    <span className={cn(
                      "status-badge",
                      u.status === 'Active' ? "status-success" : "bg-muted text-muted-foreground"
                    )}>
                      {u.status}
                    </span>
                  </td>
                  <td className="text-muted-foreground">{u.lastActive}</td>
                  <td>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="p-2 rounded-lg hover:bg-muted transition-colors">
                          <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem className="cursor-pointer">
                          <Mail className="w-4 h-4 mr-2" />
                          Send Email
                        </DropdownMenuItem>
                        <DropdownMenuItem className="cursor-pointer">
                          <Shield className="w-4 h-4 mr-2" />
                          Change Role
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
          <p className="text-sm text-muted-foreground">
            Showing {filteredUsers.length} of {mockUsers.length} users
          </p>
          <div className="flex items-center gap-2">
            <button className="btn-secondary py-1.5 px-3 text-sm" disabled>Previous</button>
            <button className="btn-secondary py-1.5 px-3 text-sm">Next</button>
          </div>
        </div>
      </div>
    </div>
  );
}
