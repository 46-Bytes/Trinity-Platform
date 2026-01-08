// This component reuses the FirmAdminDashboard logic from DashboardHome
// It shows the same overview that firm admin sees
import { useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchFirmStats, fetchFirmAdvisors, fetchFirmClientsById } from '@/store/slices/firmReducer';
import { fetchSubscriptions } from '@/store/slices/subscriptionReducer';
import { StatCard } from '@/components/ui/stat-card';
import { 
  Users, 
  FolderOpen, 
  CheckSquare, 
  Clock
} from 'lucide-react';

interface FirmDetailsContext {
  firmId: string;
}

export default function FirmDetailsOverview() {
  const { firmId } = useOutletContext<FirmDetailsContext>();
  const dispatch = useAppDispatch();
  const { firm, advisors, clients, stats, isLoading } = useAppSelector((state) => state.firm);
  const { subscriptions } = useAppSelector((state) => state.subscription);

  useEffect(() => {
    if (firmId) {
      dispatch(fetchFirmStats(firmId));
      dispatch(fetchFirmAdvisors(firmId));
      dispatch(fetchFirmClientsById(firmId));
      dispatch(fetchSubscriptions());
    }
  }, [dispatch, firmId]);

  return (
    <div className="space-y-6">
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Clock className="w-6 h-6 animate-spin text-accent" />
          <span className="ml-2 text-muted-foreground">Loading analytics...</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard 
              title="Total Advisors" 
              value={advisors.length.toString()} 
              change={advisors.filter(a => a.is_active).length > 0 ? `${advisors.filter(a => a.is_active).length} active` : undefined}
              changeType="positive"
              icon={Users}
            />
            <StatCard 
              title="Seats Used" 
              value={`${firm?.seats_used ?? 0} / ${firm?.seat_count ?? 0}`}
              change={firm ? `${firm.seat_count - firm.seats_used} available` : undefined}
              changeType="positive"
              icon={Users}
            />
            <StatCard 
              title="Total Engagements" 
              value={stats?.engagements_count?.toString() || '0'} 
              change={stats?.active_engagements ? `${stats.active_engagements} active` : undefined}
              changeType="positive"
              icon={FolderOpen}
            />
            <StatCard 
              title="Pending Tasks" 
              value={stats?.tasks_count?.toString() || '0'} 
              icon={CheckSquare}
            />
          </div>

          <div className="card-trinity p-6">
            <h3 className="font-heading font-semibold text-lg mb-4">Firm Overview</h3>
            <p className="text-muted-foreground mb-4">
              Manage advisors, clients, engagements, and monitor firm activity.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
              <div className="p-4 bg-muted/30 rounded-lg">
                <div className="text-2xl font-bold text-foreground">{stats?.engagements_count || 0}</div>
                <div className="text-sm text-muted-foreground mt-1">Total Engagements</div>
              </div>
              <div className="p-4 bg-muted/30 rounded-lg">
                <div className="text-2xl font-bold text-foreground">{stats?.tasks_count || 0}</div>
                <div className="text-sm text-muted-foreground mt-1">Total Tasks</div>
              </div>
              <div className="p-4 bg-muted/30 rounded-lg">
                <div className="text-2xl font-bold text-foreground">{stats?.diagnostics_count || 0}</div>
                <div className="text-sm text-muted-foreground mt-1">Diagnostics</div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

