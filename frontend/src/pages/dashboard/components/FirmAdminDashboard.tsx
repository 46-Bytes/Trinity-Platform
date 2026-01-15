import { useEffect } from 'react';
import { StatCard } from '@/components/ui/stat-card';
import { 
  Users, 
  FolderOpen, 
  Calendar
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { fetchFirm, fetchFirmAdvisors, fetchFirmClients, fetchFirmStats } from '@/store/slices/firmReducer';
import { fetchSubscriptions } from '@/store/slices/subscriptionReducer';

export function FirmAdminDashboard() {
  const dispatch = useAppDispatch();
  const { firm, advisors, clients, stats, isLoading } = useAppSelector((state) => state.firm);
  const { subscriptions } = useAppSelector((state) => state.subscription);

  useEffect(() => {
    if (!firm) {
      dispatch(fetchFirm());
    }
  }, [dispatch, firm]);

  useEffect(() => {
    if (firm?.id) {
      dispatch(fetchFirmAdvisors(firm.id));
      dispatch(fetchFirmClients());
      dispatch(fetchFirmStats(firm.id));
      dispatch(fetchSubscriptions());
    }
  }, [dispatch, firm?.id]);

  // Total advisors includes all Firm Advisors (active + suspended), NOT including Firm Admin
  const totalAdvisors = stats?.advisors_count ?? advisors.length;
  // Seats used should only count active Firm Advisors (Firm Admin does NOT count toward seats)
  const seatsUsed = stats?.seats_used ?? advisors.filter((a) => a.is_active).length;
  const seatCount = firm?.seat_count ?? 0;
  // Use stats for available seats to ensure consistency
  const availableSeats = stats?.seats_available ?? Math.max(seatCount - seatsUsed, 0);
  const totalClients = clients.length;
  const activeEngagements = stats?.active_engagements ?? 0;

  // Calculate subscription days remaining
  const calculateSubscriptionDays = () => {
    // Find subscription for this firm (match by firm_id or check if firm has subscription_id)
    const firmSubscription = subscriptions.find((sub) => 
      sub.firm_id === firm?.id || sub.id === (firm as any)?.subscription_id
    );
    
    if (!firmSubscription) {
      return null;
    }

    // Use current_period_end if available, otherwise calculate from created_at + 30 days
    let endDate: Date;
    
    if (firmSubscription.current_period_end) {
      endDate = new Date(firmSubscription.current_period_end);
    } else {
      // Fallback: calculate from created_at + 30 days (monthly subscription)
      const createdDate = new Date(firmSubscription.created_at);
      endDate = new Date(createdDate);
      endDate.setDate(endDate.getDate() + 30);
    }

    const now = new Date();
    const diffTime = endDate.getTime() - now.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    return diffDays;
  };

  const subscriptionDays = calculateSubscriptionDays();
  
  // Format subscription days display
  const getSubscriptionDisplay = () => {
    if (subscriptionDays === null) {
      return { value: 'N/A', iconColor: 'text-muted-foreground' };
    }
    
    if (subscriptionDays < 0) {
      return { 
        value: 'Expired', 
        iconColor: 'text-destructive',
        change: `${Math.abs(subscriptionDays)} days overdue`,
        changeType: 'negative' as const
      };
    }
    
    if (subscriptionDays < 3) {
      return { 
        value: `${subscriptionDays} ${subscriptionDays === 1 ? 'day' : 'days'}`,
        iconColor: 'text-orange-500',
        change: 'Expiring soon',
        changeType: 'negative' as const
      };
    }
    
    return { 
      value: `${subscriptionDays} ${subscriptionDays === 1 ? 'day' : 'days'}`,
      iconColor: 'text-accent',
      change: 'Remaining',
      changeType: 'neutral' as const
    };
  };

  const subscriptionDisplay = getSubscriptionDisplay();

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          title="Firm Advisors" 
          value={String(totalAdvisors)} 
          change={`${availableSeats} available seats`} 
          changeType="neutral"
          icon={Users}
        />
        <StatCard 
          title="Total Clients" 
          value={String(totalClients)} 
          icon={Users}
        />
        <StatCard 
          title="Active Engagements" 
          value={String(activeEngagements)} 
          icon={FolderOpen}
        />
        <StatCard 
          title="Subscription Days" 
          value={subscriptionDisplay.value}
          change={subscriptionDisplay.change}
          changeType={subscriptionDisplay.changeType}
          icon={Calendar}
          iconColor={subscriptionDisplay.iconColor}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card-trinity p-6">
          <h3 className="font-heading font-semibold text-lg mb-4">Advisor Overview</h3>
          <div className="space-y-3">
            {isLoading && advisors.length === 0 && (
              <p className="text-sm text-muted-foreground">Loading advisors...</p>
            )}
            {!isLoading && advisors.length === 0 && (
              <p className="text-sm text-muted-foreground">No advisors yet. Add advisors to your firm to get started.</p>
            )}
            {advisors.map((advisor, i) => (
              <div key={advisor.id || i} className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
                <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-medium">
                  {advisor.name.charAt(0)}
                </div>
                <div className="flex-1">
                  <p className="font-medium text-sm">{advisor.name}</p>
                  <p className="text-xs text-muted-foreground">{advisor.email}</p>
                </div>
                <span className={cn(
                  "status-badge",
                  advisor.is_active ? "status-success" : "status-warning"
                )}>
                  {advisor.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="card-trinity p-6">
          <h3 className="font-heading font-semibold text-lg mb-4">Billing & Subscription</h3>
          <div className="space-y-4">
            <div className="p-4 rounded-lg bg-accent/5 border border-accent/20">
              <p className="text-sm font-medium">Professional Plan</p>
              <p className="text-2xl font-heading font-bold mt-1">$299<span className="text-sm font-normal text-muted-foreground">/month</span></p>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Seats used</span>
              <span className="font-medium">{stats?.seats_used ?? seatsUsed} / {seatCount || '-'}</span>
            </div>
            {stats?.seats_available !== undefined && (
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Seats available</span>
                <span className="font-medium">{stats.seats_available}</span>
              </div>
            )}
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Next billing</span>
              <span className="font-medium">Jan 1, 2025</span>
            </div>
            <button className="btn-secondary w-full">Manage Subscription</button>
          </div>
        </div>
      </div>
    </div>
  );
}

