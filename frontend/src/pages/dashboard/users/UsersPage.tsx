import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { roleLabels, roleColors, UserRole } from '@/types/auth';
import { Search, Plus, MoreHorizontal, Loader2, Edit, UserPlus, Eye, UserCog } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchUsers, createUser, updateUser } from '@/store/slices/userReducer';
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
} from "@/components/ui/dialog";
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
import { toast } from 'sonner';
import { AdvisorClientDialog } from '@/components/users/AdvisorClientDialog';
import type { User } from '@/store/slices/userReducer';

export default function UsersPage() {
  const { user, startImpersonation, isImpersonating } = useAuth();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { users, isLoading, isCreating, isUpdating, error } = useAppSelector((state) => state.user);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<UserRole | 'all'>('all');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedAdvisor, setSelectedAdvisor] = useState<User | null>(null);
  const [isAssociationDialogOpen, setIsAssociationDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  
  // Form state
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserName, setNewUserName] = useState('');
  const [newUserRole, setNewUserRole] = useState<UserRole>('client');

  // Fetch users on mount
  useEffect(() => {
    dispatch(fetchUsers());
  }, [dispatch]);

  // Show error toast if there's an error
  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  const handleCreateUser = async () => {
    if (!newUserEmail || !newUserName) {
      toast.error('Please fill in all required fields');
      return;
    }

    try {
      await dispatch(createUser({
        email: newUserEmail,
        name: newUserName,
        role: newUserRole,
      })).unwrap();
      
      toast.success('User created successfully');
      setIsDialogOpen(false);
      setNewUserEmail('');
      setNewUserName('');
      setNewUserRole('client');
    } catch (error) {

    }
  };

  const handleEditUser = (user: User) => {
    setEditingUser(user);
    setNewUserName(user.name);
    setNewUserRole(user.role);
    setNewUserEmail(user.email);
    setIsDialogOpen(true);
  };

  const handleUpdateUser = async () => {
    if (!editingUser || !newUserName) {
      toast.error('Please fill in all required fields');
      return;
    }

    try {
      await dispatch(updateUser({
        id: editingUser.id,
        name: newUserName,
        role: newUserRole,
      })).unwrap();
      
      toast.success('User updated successfully');
      setIsDialogOpen(false);
      setEditingUser(null);
      setNewUserEmail('');
      setNewUserName('');
      setNewUserRole('client');
    } catch (error) {

    }
  };

  const handleDialogClose = (open: boolean) => {
    setIsDialogOpen(open);
    if (!open) {
      setEditingUser(null);
      setNewUserEmail('');
      setNewUserName('');
      setNewUserRole('client');
    }
  };

  const filteredUsers = users.filter(u => {
    const matchesSearch = u.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesRole = roleFilter === 'all' || u.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return 'N/A';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">User Management</h1>
          <p className="text-muted-foreground mt-1">Manage platform users and their roles</p>
        </div>
        <button 
          className="btn-primary"
          onClick={() => setIsDialogOpen(true)}
        >
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
          <Select 
            value={roleFilter} 
            onValueChange={(value) => setRoleFilter(value as UserRole | 'all')}
          >
            <SelectTrigger className="w-full sm:w-48">
              <SelectValue placeholder="All Roles" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Roles</SelectItem>
              {user?.role === 'super_admin' ? (
                // For super_admin, show all roles including firm_admin and firm_advisor
                Object.entries(roleLabels).map(([key, label]) => (
                  <SelectItem key={key} value={key}>{label}</SelectItem>
                ))
              ) : (
                // For other roles, exclude firm_admin and firm_advisor
                Object.entries(roleLabels)
                  .filter(([key]) => key !== 'firm_admin' && key !== 'firm_advisor')
                  .map(([key, label]) => (
                    <SelectItem key={key} value={key}>{label}</SelectItem>
                  ))
              )}
            </SelectContent>
          </Select>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
            <span className="ml-2 text-muted-foreground">Loading users...</span>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="table-trinity">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Email Verified</th>
                    <th>Last Active</th>
                    <th className="w-12"></th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((u) => (
                    <tr key={u.id} className="group">
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
                          {user?.role === 'super_admin' 
                            ? (u.role === 'client' && u.firm_id 
                                ? 'Firm Client' 
                                : roleLabels[u.role])
                            : roleLabels[u.role]}
                        </span>
                      </td>
                      <td>
                        <span className={cn(
                          "status-badge",
                          u.is_active ? "status-success" : "bg-muted text-muted-foreground"
                        )}>
                          {u.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td>
                        <span className={cn(
                          "status-badge",
                          u.email_verified ? "status-success" : "bg-yellow-100 text-yellow-800"
                        )}>
                          {u.email_verified ? 'Verified' : 'Unverified'}
                        </span>
                      </td>
                      <td className="text-muted-foreground">
                        {u.last_login ? formatDate(u.last_login) : 'Never'}
                      </td>
                      <td>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="p-1.5 rounded-lg hover:bg-muted transition-colors opacity-0 group-hover:opacity-100">
                              <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {user?.role === 'super_admin' && (
                              <DropdownMenuItem 
                                className="cursor-pointer"
                                onClick={() => navigate(`/dashboard/users/${u.id}`)}
                              >
                                <Eye className="w-4 h-4 mr-2" />
                                View Details
                              </DropdownMenuItem>
                            )}
                            {user?.role === 'super_admin' && !isImpersonating && u.role !== 'super_admin' && (
                              <DropdownMenuItem
                                className="cursor-pointer"
                                onClick={async () => {
                                  try {
                                    await startImpersonation(u.id);
                                    // Redirect happens automatically in startImpersonation
                                  } catch (error) {
                                    toast.error('Failed to start impersonation');
                                    console.error('Error starting impersonation:', error);
                                  }
                                }}
                              >
                                <UserCog className="w-4 h-4 mr-2" />
                                Impersonate
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem 
                              className="cursor-pointer"
                              onClick={() => handleEditUser(u)}
                            >
                              <Edit className="w-4 h-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            {u.role === 'advisor' && (
                              <DropdownMenuItem
                                className="cursor-pointer"
                                onClick={() => {
                                  setSelectedAdvisor(u);
                                  setIsAssociationDialogOpen(true);
                                }}
                              >
                                <UserPlus className="w-4 h-4 mr-2" />
                                Associate Client
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {filteredUsers.length === 0 && !isLoading && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No users found</p>
                {searchQuery && (
                  <p className="text-sm text-muted-foreground mt-2">
                    Try adjusting your search or filters
                  </p>
                )}
              </div>
            )}

            <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
              <p className="text-sm text-muted-foreground">
                Showing {filteredUsers.length} of {users.length} users
              </p>
            </div>
          </>
        )}
      </div>

      {/* Add/Edit User Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={handleDialogClose}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>{editingUser ? 'Edit User' : 'Add New User'}</DialogTitle>
            <DialogDescription>
              {editingUser 
                ? 'Update user information. Email cannot be changed.'
                : 'Create a new user account. The user will need to set up Auth0 authentication later.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address *</Label>
              <Input
                id="email"
                type="email"
                placeholder="user@example.com"
                value={newUserEmail}
                onChange={(e) => setNewUserEmail(e.target.value)}
                disabled={!!editingUser}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Full Name *</Label>
              <Input
                id="name"
                type="text"
                placeholder="John Doe"
                value={newUserName}
                onChange={(e) => setNewUserName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <Select value={newUserRole} onValueChange={(value) => setNewUserRole(value as UserRole)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="client">Client</SelectItem>
                  <SelectItem value="advisor">Advisor</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button
              variant="outline"
              onClick={() => handleDialogClose(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={editingUser ? handleUpdateUser : handleCreateUser}
              disabled={(isCreating || isUpdating) || !newUserEmail || !newUserName}
            >
              {(isCreating || isUpdating) ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {editingUser ? 'Updating...' : 'Creating...'}
                </>
              ) : (
                editingUser ? 'Update User' : 'Create User'
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Advisor-Client Association Dialog */}
      {selectedAdvisor && (
        <AdvisorClientDialog
          open={isAssociationDialogOpen}
          onOpenChange={(open) => {
            setIsAssociationDialogOpen(open);
            if (!open) {
              setSelectedAdvisor(null);
            }
          }}
          advisor={selectedAdvisor}
        />
      )}
    </div>
  );
}
