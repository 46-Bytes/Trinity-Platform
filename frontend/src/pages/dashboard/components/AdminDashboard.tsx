import { useEffect } from 'react';
import { StatCard } from '@/components/ui/stat-card';
import { 
  Users, 
  UserCheck,
  Briefcase,
  Clock,
  FolderOpen
} from 'lucide-react';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { fetchUsers } from '@/store/slices/userReducer';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import { fetchTasks } from '@/store/slices/tasksReducer';

export function AdminDashboard() {
  const dispatch = useAppDispatch();
  const { users, isLoading: usersLoading } = useAppSelector((state) => state.user);
  const { engagements, isLoading: engagementsLoading } = useAppSelector((state) => state.engagement);
  const { tasks, isLoading: tasksLoading } = useAppSelector((state) => state.task);
  
  // Fetch data on mount
  useEffect(() => {
    dispatch(fetchUsers({ limit: 1000 }));
    dispatch(fetchEngagements({}));
    dispatch(fetchTasks({ limit: 1000 }));
  }, [dispatch]);
  
  // Calculate stat card metrics
  const totalUsers = users.length;
  const totalEngagements = engagements.length;
  
  // Clients: users with role='client' and no firm_id (not in form)
  const clients = users.filter(u => u.role === 'client' && !u.firm_id).length;
  
  // Advisors: users with role='advisor' (not 'firm_advisor')
  const advisors = users.filter(u => u.role === 'advisor').length;
  
  // Calculate Platform Overview metrics (different from stat cards)
  const totalTasks = tasks.length;
  const pendingTasks = tasks.filter(t => t.status === 'pending' || t.status === 'in_progress').length;
  const activeEngagements = engagements.filter(e => e.status === 'active').length;
  const completedEngagements = engagements.filter(e => e.status === 'completed').length;
  
  const isLoading = usersLoading || engagementsLoading || tasksLoading;

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
              title="Total Users" 
              value={totalUsers.toString()} 
              icon={Users}
            />
            <StatCard 
              title="Total Engagements" 
              value={totalEngagements.toString()} 
              icon={FolderOpen}
            />
            <StatCard 
              title="Clients" 
              value={clients.toString()}
              change="Not in firm"
              changeType="neutral"
              icon={UserCheck}
            />
            <StatCard 
              title="Advisors" 
              value={advisors.toString()}
              change="Not firm advisors"
              changeType="neutral"
              icon={Briefcase}
            />
          </div>

          <div className="card-trinity p-6">
            <h3 className="font-heading font-semibold text-lg mb-4">Platform Overview</h3>
            <p className="text-muted-foreground mb-4">
              Manage users, tasks, and monitor platform activity. Note: As an Admin, you cannot view client engagement files.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-4">
              <div className="p-4 bg-muted/30 rounded-lg">
                <div className="text-2xl font-bold text-foreground">{totalTasks}</div>
                <div className="text-sm text-muted-foreground mt-1">Total Tasks</div>
              </div>
              <div className="p-4 bg-muted/30 rounded-lg">
                <div className="text-2xl font-bold text-foreground">{pendingTasks}</div>
                <div className="text-sm text-muted-foreground mt-1">Pending Tasks</div>
              </div>
              <div className="p-4 bg-muted/30 rounded-lg">
                <div className="text-2xl font-bold text-foreground">{activeEngagements}</div>
                <div className="text-sm text-muted-foreground mt-1">Active Engagements</div>
              </div>
              <div className="p-4 bg-muted/30 rounded-lg">
                <div className="text-2xl font-bold text-foreground">{completedEngagements}</div>
                <div className="text-sm text-muted-foreground mt-1">Completed Engagements</div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

