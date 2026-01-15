import { useEffect } from 'react';
import { StatCard } from '@/components/ui/stat-card';
import { 
  FolderOpen, 
  CheckSquare, 
  Brain,
  Clock
} from 'lucide-react';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import { fetchTasks } from '@/store/slices/tasksReducer';

export function AdminDashboard() {
  const dispatch = useAppDispatch();
  const { engagements, isLoading: engagementsLoading } = useAppSelector((state) => state.engagement);
  const { tasks, isLoading: tasksLoading } = useAppSelector((state) => state.task);
  
  // Fetch data on mount
  useEffect(() => {
    dispatch(fetchEngagements({}));
    dispatch(fetchTasks({ limit: 1000 }));
  }, [dispatch]);
  
  // Calculate real analytics
  const pendingTasks = tasks.filter(t => t.status === 'pending' || t.status === 'in_progress').length;
  const activeEngagements = engagements.filter(e => e.status === 'active').length;
  const totalEngagements = engagements.length;
  const completedEngagements = engagements.filter(e => e.status === 'completed').length;
  
  // Calculate AI requests (diagnostics completed)
  const diagnosticsCount = engagements.reduce((sum, e) => sum + (e.diagnosticsCount || 0), 0);
  
  const isLoading = engagementsLoading || tasksLoading;

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
              title="Total Engagements" 
              value={totalEngagements.toString()} 
              change={activeEngagements > 0 ? `${activeEngagements} active` : undefined}
              changeType="positive"
              icon={FolderOpen}
            />
            <StatCard 
              title="Active Engagements" 
              value={activeEngagements.toString()}
              icon={FolderOpen}
            />
            <StatCard 
              title="Pending Tasks" 
              value={pendingTasks.toString()} 
              icon={CheckSquare}
            />
            <StatCard 
              title="Diagnostics" 
              value={diagnosticsCount.toString()}
              change={completedEngagements > 0 ? `${completedEngagements} completed` : undefined}
              changeType="positive"
              icon={Brain}
            />
          </div>

          <div className="card-trinity p-6">
            <h3 className="font-heading font-semibold text-lg mb-4">Platform Overview</h3>
            <p className="text-muted-foreground mb-4">
              Manage engagements, tasks, and monitor platform activity. Note: As an Admin, you cannot view client engagement files.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
              <div className="p-4 bg-muted/30 rounded-lg">
                <div className="text-2xl font-bold text-foreground">{totalEngagements}</div>
                <div className="text-sm text-muted-foreground mt-1">Total Engagements</div>
              </div>
              <div className="p-4 bg-muted/30 rounded-lg">
                <div className="text-2xl font-bold text-foreground">{pendingTasks}</div>
                <div className="text-sm text-muted-foreground mt-1">Pending Tasks</div>
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

