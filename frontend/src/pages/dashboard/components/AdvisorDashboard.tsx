import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { StatCard } from '@/components/ui/stat-card';
import { 
  Users, 
  FolderOpen, 
  FileText,
  Clock,
  ArrowRight
} from 'lucide-react';
import { cn, getUniqueClientIds } from '@/lib/utils';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import { fetchTasks } from '@/store/slices/tasksReducer';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface FirmAdvisorDashboardStats {
  active_clients: number;
  total_engagements: number;
  total_documents: number;
  total_tasks: number;
  total_diagnostics: number;
}

export function AdvisorDashboard() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { engagements, isLoading: engagementsLoading } = useAppSelector((state) => state.engagement);
  const { tasks, isLoading: tasksLoading } = useAppSelector((state) => state.task);
  
  const isFirmAdvisor = user?.role === 'firm_advisor';
  const [firmAdvisorStats, setFirmAdvisorStats] = useState<FirmAdvisorDashboardStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);
  
  // Fetch data on mount
  useEffect(() => {
    dispatch(fetchEngagements({}));
    dispatch(fetchTasks({ limit: 1000 }));
  }, [dispatch]);
  
  // Fetch firm advisor stats from API
  useEffect(() => {
    if (isFirmAdvisor) {
      const fetchFirmAdvisorStats = async () => {
        try {
          setIsLoadingStats(true);
          const token = localStorage.getItem('auth_token');
          if (!token) {
            throw new Error('No authentication token found');
          }

          const response = await fetch(`${API_BASE_URL}/api/dashboard/stats`, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch dashboard stats' }));
            throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch dashboard stats`);
          }

          const data = await response.json();
          setFirmAdvisorStats(data);
        } catch (err) {
          console.error('Failed to fetch firm advisor dashboard stats:', err);
        } finally {
          setIsLoadingStats(false);
        }
      };

      fetchFirmAdvisorStats();
    }
  }, [isFirmAdvisor]);
  
  // Calculate real analytics
  // For firm_advisor, use API stats; for regular advisor, calculate from Redux state
  const uniqueClients = isFirmAdvisor && firmAdvisorStats 
    ? firmAdvisorStats.active_clients 
    : getUniqueClientIds(engagements).size;
  const totalEngagements = isFirmAdvisor && firmAdvisorStats 
    ? firmAdvisorStats.total_engagements 
    : engagements.length;
  const totalDocuments = isFirmAdvisor && firmAdvisorStats 
    ? firmAdvisorStats.total_documents 
    : engagements.reduce((sum, e) => sum + (e.documentsCount || 0), 0);
  const pendingTasks = tasks.filter(t => t.status === 'pending' || t.status === 'in_progress').length;
  
  const isLoading = engagementsLoading || tasksLoading || (isFirmAdvisor && isLoadingStats);

  // Calculate progress percentage (tasks completed / total tasks)
  const calculateProgress = (engagement: typeof engagements[0]) => {
    const totalTasks = engagement.tasksCount || 0;
    const completedTasks = totalTasks - (engagement.pendingTasksCount || 0);
    if (totalTasks === 0) return 0;
    return Math.round((completedTasks / totalTasks) * 100);
  };

  // Format status for display
  const formatStatus = (status: string) => {
    const statusMap: Record<string, string> = {
      'active': 'Active',
      'draft': 'Draft',
      'on-hold': 'In Review',
      'completed': 'Completed',
      'cancelled': 'Archived',
    };
    return statusMap[status.toLowerCase()] || status;
  };

  // Get status badge class
  const getStatusBadgeClass = (status: string) => {
    const statusLower = status.toLowerCase();
    if (statusLower === 'active') return 'status-success';
    if (statusLower === 'on-hold' || statusLower === 'draft') return 'status-info';
    if (statusLower === 'completed') return 'status-success';
    return 'bg-muted text-muted-foreground';
  };

  // Get upcoming tasks (pending or in_progress, sorted by due date)
  const upcomingTasks = tasks
    .filter(t => t.status === 'pending' || t.status === 'in_progress')
    .sort((a, b) => {
      if (!a.dueDate && !b.dueDate) return 0;
      if (!a.dueDate) return 1;
      if (!b.dueDate) return -1;
      return new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime();
    })
    .slice(0, 3); // Show only top 3

  // Format task due date
  const formatTaskDueDate = (dueDate?: string) => {
    if (!dueDate) return 'No due date';
    const date = new Date(dueDate);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const taskDate = new Date(date);
    taskDate.setHours(0, 0, 0, 0);
    const diffTime = taskDate.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Tomorrow';
    if (diffDays === -1) return 'Yesterday';
    if (diffDays < 0) return `${Math.abs(diffDays)} days ago`;
    if (diffDays <= 7) {
      const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
      return days[date.getDay()];
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Get top 5 engagements for display
  const displayEngagements = engagements.slice(0, 5);

  return (
    <div className="space-y-6">
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Clock className="w-6 h-6 animate-spin text-accent" />
          <span className="ml-2 text-muted-foreground">Loading analytics...</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <StatCard 
              title="Active Clients" 
              value={uniqueClients.toString()} 
              icon={Users}
            />
            <StatCard 
              title="Engagements" 
              value={totalEngagements.toString()}
              icon={FolderOpen}
            />
            <StatCard 
              title="Documents" 
              value={totalDocuments.toString()} 
              icon={FileText}
            />
          </div>
        </>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card-trinity p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-heading font-semibold text-lg">Client Engagements</h3>
            <button 
              className="btn-trinity text-accent hover:bg-accent/10"
              onClick={() => navigate('/dashboard/engagements')}
            >
              View all <ArrowRight className="w-4 h-4 ml-1" />
            </button>
          </div>
          <div className="overflow-x-auto">
            {displayEngagements.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p>No engagements found</p>
              </div>
            ) : (
              <table className="table-trinity">
                <thead>
                  <tr>
                    <th>Client</th>
                    <th>Status</th>
                    <th>Progress</th>
                    <th>Tasks</th>
                  </tr>
                </thead>
                <tbody>
                  {displayEngagements.map((eng) => {
                    const progress = calculateProgress(eng);
                    return (
                      <tr 
                        key={eng.id} 
                        className="cursor-pointer hover:bg-muted/50 transition-colors"
                        onClick={() => navigate(`/dashboard/engagements/${eng.id}`)}
                      >
                        <td className="font-medium">{eng.clientName || 'Unknown Client'}</td>
                        <td>
                          <span className={cn("status-badge", getStatusBadgeClass(eng.status))}>
                            {formatStatus(eng.status)}
                          </span>
                        </td>
                        <td>
                          <div className="flex items-center gap-3">
                            <div className="progress-trinity w-24">
                              <div className="progress-trinity-bar" style={{ width: `${progress}%` }} />
                            </div>
                            <span className="text-sm text-muted-foreground">{progress}%</span>
                          </div>
                        </td>
                        <td>
                          <span className="text-sm">
                            {eng.tasksCount || 0} total • <span className="text-warning">{eng.pendingTasksCount || 0} pending</span>
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="card-trinity p-6">
            <h3 className="font-heading font-semibold text-lg mb-4">Upcoming Tasks</h3>
            <div className="space-y-3">
              {upcomingTasks.length === 0 ? (
                <div className="text-center py-4 text-sm text-muted-foreground">
                  No upcoming tasks
                </div>
              ) : (
                upcomingTasks.map((task) => {
                  const dueDate = formatTaskDueDate(task.dueDate);
                  const isToday = dueDate === 'Today';
                  const isOverdue = task.dueDate && new Date(task.dueDate) < new Date() && task.status !== 'completed';
                  return (
                    <div 
                      key={task.id} 
                      className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                      onClick={() => navigate('/dashboard/tasks')}
                    >
                      <div className={cn(
                        "w-2 h-2 rounded-full flex-shrink-0",
                        isOverdue ? "bg-destructive" : isToday ? "bg-warning" : "bg-accent"
                      )} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{task.title}</p>
                        <p className="text-xs text-muted-foreground">{task.engagementName || 'No engagement'}</p>
                      </div>
                      <span className={cn(
                        "text-xs font-medium",
                        isOverdue && "text-destructive",
                        isToday && !isOverdue && "text-warning"
                      )}>{dueDate}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

