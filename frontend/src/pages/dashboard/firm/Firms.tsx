import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Search, Loader2, Building2, Users, Briefcase, Mail, Plus, Ban, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchFirms, revokeFirm, reactivateFirm } from '@/store/slices/firmReducer';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { CreateFirmDialog } from '@/components/firms/CreateFirmDialog';
import { RevokeFirmDialog } from '@/components/firms/RevokeFirmDialog';

export default function FirmsPage() {
  const { user } = useAuth();
  const dispatch = useAppDispatch();
  const { firms, isLoading, error } = useAppSelector((state) => state.firm);
  const navigate = useNavigate();
  
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);
  const [firmToRevoke, setFirmToRevoke] = useState<{ id: string; name: string } | null>(null);

  // Check if user is superadmin
  const isSuperAdmin = user?.role === 'super_admin';

  // Fetch firms on mount (only for superadmin)
  useEffect(() => {
    if (isSuperAdmin) {
      dispatch(fetchFirms());
    }
  }, [dispatch, isSuperAdmin]);

  // Show error toast if there's an error
  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  // Filter firms based on search query
  const filteredFirms = firms.filter(firm => {
    const matchesSearch = !searchQuery || 
      firm.firm_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      firm.firm_admin_email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      firm.billing_email?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  // Format date for display
  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return 'N/A';
    }
  };

  // If not superadmin, show access denied
  if (!isSuperAdmin) {
    return (
      <div className="space-y-6">
        <div className="card-trinity p-6">
          <div className="text-center py-12">
            <p className="text-destructive mb-2">Access Denied</p>
            <p className="text-sm text-muted-foreground">
              You need super admin privileges to view this page.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const handleCreateSuccess = () => {
    dispatch(fetchFirms());
  };

  const handleRevokeFirmClick = (firmId: string, firmName: string) => {
    setFirmToRevoke({ id: firmId, name: firmName });
    setRevokeDialogOpen(true);
  };

  const handleReactivateFirm = async (firmId: string) => {
    try {
      await dispatch(reactivateFirm(firmId)).unwrap();
      toast.success('Firm reactivated successfully');
      dispatch(fetchFirms());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to reactivate firm');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Firm Management</h1>
          <p className="text-muted-foreground mt-1">View and manage all firms on the platform</p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)} className="flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Create Firm
        </Button>
      </div>

      <div className="card-trinity p-6">
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search firms by name, admin email, or billing email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-trinity pl-10 w-full"
            />
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
            <span className="ml-2 text-muted-foreground">Loading firms...</span>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="table-trinity">
                <thead>
                  <tr>
                    <th>Firm</th>
                    <th>Admin</th>
                    <th>Seats</th>
                    <th>Advisors</th>
                    <th>Clients</th>
                    <th>Billing Email</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFirms.map((firm) => (
                    <tr 
                      key={firm.id} 
                      className="group cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => navigate(`/dashboard/firms/${firm.id}/clients`)}
                    >
                      <td>
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground">
                            <Building2 className="w-5 h-5" />
                          </div>
                          <div>
                            <p className="font-medium">{firm.firm_name}</p>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div>
                          <p className="font-medium">{firm.firm_admin_name || 'N/A'}</p>
                        </div>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            "font-medium",
                            firm.seats_used >= firm.seat_count && "text-destructive"
                          )}>
                            {firm.seats_used} / {firm.seat_count}
                          </span>
                          {firm.seats_used >= firm.seat_count && (
                            <span className="status-badge bg-red-100 text-red-700 text-xs">
                              Full
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <Users className="w-4 h-4 text-muted-foreground" />
                          <span className="font-medium">{firm.advisors_count || 0}</span>
                        </div>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <Briefcase className="w-4 h-4 text-muted-foreground" />
                          <span className="font-medium">{firm.clients_count || 0}</span>
                        </div>
                      </td>
                      <td>
                        {firm.billing_email ? (
                          <div className="flex items-center gap-2">
                            <Mail className="w-4 h-4 text-muted-foreground" />
                            <span className="text-sm">{firm.billing_email}</span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-sm">N/A</span>
                        )}
                      </td>
                      <td className="text-muted-foreground text-sm">
                        {formatDate(firm.created_at)}
                      </td>
                      <td>
                        {isSuperAdmin && (
                          <>
                            {firm.is_active !== false ? (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 px-2 text-destructive hover:text-destructive hover:bg-destructive/10"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleRevokeFirmClick(firm.id, firm.firm_name);
                                }}
                                title="Revoke Firm"
                              >
                                <Ban className="w-4 h-4" />
                              </Button>
                            ) : (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 px-2 text-green-600 hover:text-green-700 hover:bg-green-50"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleReactivateFirm(firm.id);
                                }}
                                title="Reactivate Firm"
                              >
                                <CheckCircle className="w-4 h-4" />
                              </Button>
                            )}
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {filteredFirms.length === 0 && !isLoading && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No firms found</p>
                {searchQuery && (
                  <p className="text-sm text-muted-foreground mt-2">
                    Try adjusting your search query
                  </p>
                )}
              </div>
            )}

            <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
              <p className="text-sm text-muted-foreground">
                Showing {filteredFirms.length} of {firms.length} firms
              </p>
            </div>
          </>
        )}
      </div>

      <CreateFirmDialog
        open={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
        onSuccess={handleCreateSuccess}
      />

      <RevokeFirmDialog
        open={revokeDialogOpen}
        onOpenChange={setRevokeDialogOpen}
        firmId={firmToRevoke?.id || null}
        firmName={firmToRevoke?.name || null}
        onSuccess={() => {
          setFirmToRevoke(null);
        }}
      />
    </div>
  );
}

