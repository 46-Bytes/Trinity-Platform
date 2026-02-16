import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { roleLabels, roleColors, UserRole } from '@/types/auth';
import { Search, Plus, MoreHorizontal, Loader2, Edit, UserPlus, Eye, UserCog } from 'lucide-react';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
  PaginationEllipsis,
} from '@/components/ui/pagination';
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
import { UserDetailDialog } from '@/components/users/UserDetailDialog';
import type { User } from '@/store/slices/userReducer';
import { sortUsersByLastEdited } from '@/lib/userSortUtils';

const USERS_PER_PAGE = 10;

export default function UsersPage() {
  const { user, startImpersonation, isImpersonating } = useAuth();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { users, totalUsers, isLoading, isCreating, isUpdating, error } = useAppSelector((state) => state.user);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<UserRole | 'all'>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedAdvisor, setSelectedAdvisor] = useState<User | null>(null);
  const [isAssociationDialogOpen, setIsAssociationDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isDetailDialogOpen, setIsDetailDialogOpen] = useState(false);
  
  // Form state
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserName, setNewUserName] = useState('');
  const [newUserRole, setNewUserRole] = useState<UserRole>('client');

  // Fetch users when page/filters change (debounced for search)
  useEffect(() => {
    const role = roleFilter === 'all' ? undefined : roleFilter;
    const skip = (currentPage - 1) * USERS_PER_PAGE;

    const handle = window.setTimeout(() => {
      dispatch(fetchUsers({ skip, limit: USERS_PER_PAGE, role, q: searchQuery }));
    }, 300);

    return () => window.clearTimeout(handle);
  }, [dispatch, currentPage, roleFilter, searchQuery]);

  useEffect(() => {
    setCurrentPage(1);
  }, [roleFilter]);

  // When searching, reset to page 1 (server-side search + pagination)
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

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
      // Navigate to first page to show newly created user at the top
      setCurrentPage(1);
      // Refresh users list for first page
      const role = roleFilter === 'all' ? undefined : roleFilter;
      dispatch(fetchUsers({ skip: 0, limit: USERS_PER_PAGE, role }));
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
      // Navigate to first page to show newly edited user at the top
      setCurrentPage(1);
      // Refresh users list for first page
      const role = roleFilter === 'all' ? undefined : roleFilter;
      dispatch(fetchUsers({ skip: 0, limit: USERS_PER_PAGE, role }));
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

  // Pagination + search are server-side; just sort what the API returns for the current page
  const sortedUsers = sortUsersByLastEdited(users);

  // Calculate pagination
  const totalPages = Math.ceil(totalUsers / USERS_PER_PAGE);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    // Scroll to top when page changes
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

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
                    <th>Last Login</th>
                    <th className="w-12"></th>
                  </tr>
                </thead>
                <tbody>
                  {sortedUsers.map((u) => (
                    <tr 
                      key={u.id} 
                      className="group cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => {
                        setSelectedUser(u);
                        setIsDetailDialogOpen(true);
                      }}
                    >
                      <td>
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-medium">
                            {u.name?.charAt(0)}
                          </div>
                          <div>
                            <p className="font-medium">{u.name || 'Unnamed User'}</p>
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
                            <button 
                              className="p-1.5 rounded-lg hover:bg-muted transition-colors opacity-0 group-hover:opacity-100"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                            {user?.role === 'super_admin' && (
                              <DropdownMenuItem 
                                className="cursor-pointer"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  navigate(`/dashboard/users/${u.id}`);
                                }}
                              >
                                <Eye className="w-4 h-4 mr-2" />
                                View Details
                              </DropdownMenuItem>
                            )}
                            {user?.role === 'super_admin' && !isImpersonating && u.role !== 'super_admin' && (
                              <DropdownMenuItem
                                className="cursor-pointer"
                                onClick={async (e) => {
                                  e.stopPropagation();
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
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditUser(u);
                              }}
                            >
                              <Edit className="w-4 h-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            {u.role === 'advisor' && (
                              <DropdownMenuItem
                                className="cursor-pointer"
                                onClick={(e) => {
                                  e.stopPropagation();
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

            {sortedUsers.length === 0 && !isLoading && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No users found</p>
                {searchQuery && (
                  <p className="text-sm text-muted-foreground mt-2">
                    Try adjusting your search or filters
                  </p>
                )}
              </div>
            )}

            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mt-6 pt-4 border-t border-border gap-4">
              <p className="text-sm text-muted-foreground">
                {totalUsers > 0 ? (
                  <>
                    Showing {(currentPage - 1) * USERS_PER_PAGE + 1} to{' '}
                    {Math.min(currentPage * USERS_PER_PAGE, totalUsers)} of {totalUsers} users
                  </>
                ) : (
                  <>No users found</>
                )}
              </p>
              
              {totalPages > 1 && (
                <Pagination className="!mx-0 !w-auto !justify-end">
                  <PaginationContent>
                    <PaginationItem>
                      <PaginationPrevious
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          if (currentPage > 1) {
                            handlePageChange(currentPage - 1);
                          }
                        }}
                        className={currentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                      />
                    </PaginationItem>
                    
                    {(() => {
                      const pages: (number | 'ellipsis')[] = [];
                      const maxVisiblePages = 3;
                      
                      if (totalPages <= maxVisiblePages) {
                        // Show all pages if total pages is 3 or fewer
                        for (let i = 1; i <= totalPages; i++) {
                          pages.push(i);
                        }
                      } else {
                        // Calculate sliding window of 3 consecutive pages
                        let start: number;
                        let end: number;
                        
                        // If we're in the last 3 pages, show the last 3 pages
                        if (currentPage > totalPages - maxVisiblePages) {
                          start = totalPages - maxVisiblePages + 1;
                          end = totalPages;
                        } else {
                          // Show current page and next 2 pages (e.g., page 1 shows 1,2,3; page 2 shows 2,3,4)
                          start = currentPage;
                          end = currentPage + maxVisiblePages - 1;
                        }
                        
                        // Add the 3 consecutive pages
                        for (let i = start; i <= end; i++) {
                          pages.push(i);
                        }
                      }
                      
                      return pages.map((page, index) => {
                        if (page === 'ellipsis') {
                          return (
                            <PaginationItem key={`ellipsis-${index}`}>
                              <PaginationEllipsis />
                            </PaginationItem>
                          );
                        }
                        return (
                          <PaginationItem key={page}>
                            <PaginationLink
                              href="#"
                              onClick={(e) => {
                                e.preventDefault();
                                handlePageChange(page);
                              }}
                              isActive={currentPage === page}
                              className="cursor-pointer"
                            >
                              {page}
                            </PaginationLink>
                          </PaginationItem>
                        );
                      });
                    })()}
                    
                    <PaginationItem>
                      <PaginationNext
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          if (currentPage < totalPages) {
                            handlePageChange(currentPage + 1);
                          }
                        }}
                        className={currentPage === totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              )}
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
              <Select
                value={newUserRole}
                onValueChange={(value) => setNewUserRole(value as UserRole)}
                disabled={!!editingUser}
              >
                <SelectTrigger disabled={!!editingUser}>
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

      {/* User Detail Dialog */}
      <UserDetailDialog
        open={isDetailDialogOpen}
        onOpenChange={setIsDetailDialogOpen}
        user={selectedUser}
      />

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
