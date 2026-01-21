import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Search, Loader2, CreditCard, DollarSign, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchSubscriptions } from '@/store/slices/subscriptionReducer';
import { CreateSubscriptionDialog } from '@/components/subscriptions/CreateSubscriptionDialog';
import { toast } from 'sonner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export default function SubscriptionsPage() {
  const { user } = useAuth();
  const dispatch = useAppDispatch();
  const { subscriptions, isLoading, error } = useAppSelector((state) => state.subscription);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // Check if user is superadmin
  const isSuperAdmin = user?.role === 'super_admin';

  // Fetch subscriptions on mount (only for superadmin)
  useEffect(() => {
    if (isSuperAdmin) {
      dispatch(fetchSubscriptions());
    }
  }, [dispatch, isSuperAdmin]);

  // Show error toast if there's an error
  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  // Filter subscriptions based on search query and status
  const filteredSubscriptions = subscriptions.filter(subscription => {
    const matchesSearch = !searchQuery || 
      subscription.plan_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      subscription.id.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || subscription.status === statusFilter;
    
    return matchesSearch && matchesStatus;
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

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  // Get status badge styling
  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'active':
        return 'status-success';
      case 'cancelled':
        return 'bg-red-100 text-red-700';
      case 'expired':
        return 'bg-gray-100 text-gray-700';
      case 'pending':
        return 'bg-yellow-100 text-yellow-700';
      case 'suspended':
        return 'bg-orange-100 text-orange-700';
      default:
        return 'bg-muted text-muted-foreground';
    }
  };

  // Handle subscription creation success
  const handleCreateSuccess = () => {
    dispatch(fetchSubscriptions());
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

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Subscription Management</h1>
          <p className="text-muted-foreground mt-1">View and manage all subscriptions on the platform</p>
        </div>
        <button 
          className="btn-primary"
          onClick={() => setIsDialogOpen(true)}
        >
          <Plus className="w-4 h-4" />
          Create Subscription
        </button>
      </div>

      <div className="card-trinity p-6">
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search subscriptions by plan name or ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-trinity pl-10 w-full"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full sm:w-48">
              <SelectValue placeholder="All Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="suspended">Suspended</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
            <span className="ml-2 text-muted-foreground">Loading subscriptions...</span>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="table-trinity">
                <thead>
                  <tr>
                    <th>Plan</th>
                    <th>Seats</th>
                    <th>Monthly Price</th>
                    <th>Status</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSubscriptions.map((subscription) => (
                    <tr key={subscription.id} className="group">
                      <td>
                        <span className="font-medium">{subscription.plan_name}</span>
                      </td>
                      <td>
                        <span className="font-medium">{subscription.seat_count}</span>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">
                            {formatCurrency(subscription.monthly_price)}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className={cn("status-badge", getStatusBadgeClass(subscription.status))}>
                          {subscription.status.charAt(0).toUpperCase() + subscription.status.slice(1)}
                        </span>
                      </td>
                      <td>
                        <span className="text-sm text-muted-foreground">
                          {formatDate(subscription.created_at)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {filteredSubscriptions.length === 0 && !isLoading && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No subscriptions found</p>
                {searchQuery && (
                  <p className="text-sm text-muted-foreground mt-2">
                    Try adjusting your search or filters
                  </p>
                )}
              </div>
            )}

            <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
              <p className="text-sm text-muted-foreground">
                Showing {filteredSubscriptions.length} of {subscriptions.length} subscriptions
              </p>
            </div>
          </>
        )}
      </div>

      {/* Create Subscription Dialog */}
      <CreateSubscriptionDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onSuccess={handleCreateSuccess}
      />
    </div>
  );
}

