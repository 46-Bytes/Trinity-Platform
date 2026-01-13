import { useAuth } from '@/context/AuthContext';
import { fetchFirm, fetchFirmAdvisors, fetchFirmClients, fetchFirmStats } from '@/store/slices/firmReducer';
import { fetchSubscriptions } from '@/store/slices/subscriptionReducer';
import { StatCard } from '@/components/ui/stat-card';
import { 
  Users, 
  FolderOpen, 
  CheckSquare, 
  FileText, 
  TrendingUp,
  Clock,
  AlertCircle,
  ArrowRight,
  Brain,
  Calendar
} from 'lucide-react';
import { cn, getUniqueClientIds } from '@/lib/utils';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import { fetchTasks } from '@/store/slices/tasksReducer';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface DashboardStats {
  total_users: number;
  total_users_change: string;
  total_users_change_type: string;
  active_engagements: number;
  active_engagements_change: string;
  active_engagements_change_type: string;
  total_firms: number;
  total_firms_change: string;
  total_firms_change_type: string;
  ai_generations: number;
  ai_generations_change: string;
  ai_generations_change_type: string;
  recent_ai_generations?: Array<{
    user_name: string;
    engagement_name: string;
    completed_at: string;
    time_ago: string;
  }>;
}

interface ClientDashboardStats {
  total_tasks: number;
  total_documents: number;
  total_diagnostics: number;
  latest_tasks: Array<{
    id: string;
    title: string;
    status: string;
    priority: string;
    engagement_name: string | null;
    created_at: string;
  }>;
  recent_documents: Array<{
    id: string;
    file_name: string;
    file_size: number | null;
    created_at: string;
  }>;
}

interface FirmAdvisorDashboardStats {
  active_clients: number;
  total_engagements: number;
  total_documents: number;
  total_tasks: number;
  total_diagnostics: number;
}

interface ActivityDataPoint {
  date: string;
  users: number;
  engagements: number;
  firms: number;
  ai_generations: number;
}

// Role-specific dashboard components
function SuperAdminDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activityData, setActivityData] = useState<ActivityDataPoint[]>([]);
  const [activityLoading, setActivityLoading] = useState(true);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [timePeriod, setTimePeriod] = useState<number>(7);

  useEffect(() => {
    const fetchDashboardStats = async () => {
      try {
        setIsLoading(true);
        setError(null);
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
        setStats(data);
      } catch (err) {
        console.error('Failed to fetch dashboard stats:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch dashboard stats');
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboardStats();
  }, []);

  useEffect(() => {
    const fetchActivityData = async () => {
      try {
        setActivityLoading(true);
        setActivityError(null);
        const token = localStorage.getItem('auth_token');
        if (!token) {
          throw new Error('No authentication token found');
        }

        const response = await fetch(`${API_BASE_URL}/api/dashboard/activity?days=${timePeriod}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch activity data' }));
          throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch activity data`);
        }

        const data = await response.json();
        setActivityData(data.data || []);
      } catch (err) {
        console.error('Failed to fetch activity data:', err);
        setActivityError(err instanceof Error ? err.message : 'Failed to fetch activity data');
      } finally {
        setActivityLoading(false);
      }
    };

    fetchActivityData();
  }, [timePeriod]);

  // Format large numbers with commas
  const formatNumber = (num: number): string => {
    return num.toLocaleString();
  };

  // Get computed CSS color values for chart
  const getComputedColor = (cssVar: string): string => {
    if (typeof window !== 'undefined') {
      const root = document.documentElement;
      const value = getComputedStyle(root).getPropertyValue(cssVar).trim();
      if (value) {
        return `hsl(${value})`;
      }
    }
    // Fallback colors
    const fallbacks: Record<string, string> = {
      '--accent': 'hsl(168, 76%, 36%)',
      '--primary': 'hsl(222, 47%, 15%)',
      '--warning': 'hsl(38, 92%, 50%)',
      '--success': 'hsl(152, 69%, 40%)',
    };
    return fallbacks[cssVar] || 'hsl(168, 76%, 36%)';
  };

  return (
    <div className="space-y-6">
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Clock className="w-6 h-6 animate-spin text-accent" />
          <span className="ml-2 text-muted-foreground">Loading dashboard stats...</span>
        </div>
      ) : error ? (
        <div className="card-trinity p-6">
          <div className="flex items-center gap-3 text-destructive">
            <AlertCircle className="w-5 h-5" />
            <p>Error loading dashboard stats: {error}</p>
          </div>
        </div>
      ) : stats ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard 
            title="Total Users" 
            value={formatNumber(stats.total_users)} 
            change={stats.total_users_change} 
            changeType={stats.total_users_change_type as "positive" | "negative" | "neutral"}
            icon={Users}
          />
          <StatCard 
            title="Active Engagements" 
            value={formatNumber(stats.active_engagements)} 
            change={stats.active_engagements_change} 
            changeType={stats.active_engagements_change_type as "positive" | "negative" | "neutral"}
            icon={FolderOpen}
          />
          <StatCard 
            title="Total Firms" 
            value={formatNumber(stats.total_firms)} 
            change={stats.total_firms_change} 
            changeType={stats.total_firms_change_type as "positive" | "negative" | "neutral"}
            icon={CheckSquare}
          />
          <StatCard 
            title="AI Generations" 
            value={formatNumber(stats.ai_generations)} 
            change={stats.ai_generations_change} 
            changeType={stats.ai_generations_change_type as "positive" | "negative" | "neutral"}
            icon={Brain}
          />
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card-trinity p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-heading font-semibold text-lg">Platform Activity</h3>
            <select 
              className="input-trinity py-1.5 px-3 text-sm w-auto"
              value={timePeriod}
              onChange={(e) => setTimePeriod(Number(e.target.value))}
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </div>
          {activityLoading ? (
            <div className="h-64 flex items-center justify-center bg-muted/30 rounded-lg">
              <Clock className="w-6 h-6 animate-spin text-accent" />
              <span className="ml-2 text-muted-foreground">Loading activity data...</span>
            </div>
          ) : activityError ? (
            <div className="h-64 flex items-center justify-center bg-muted/30 rounded-lg">
              <div className="flex items-center gap-3 text-destructive">
                <AlertCircle className="w-5 h-5" />
                <p className="text-sm">Error loading activity data: {activityError}</p>
              </div>
            </div>
          ) : activityData.length === 0 ? (
            <div className="h-64 flex items-center justify-center bg-muted/30 rounded-lg">
              <p className="text-muted-foreground">No activity data available</p>
            </div>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={activityData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis 
                    dataKey="date" 
                    stroke="hsl(var(--muted-foreground))"
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                    tickFormatter={(value) => {
                      const date = new Date(value);
                      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    }}
                  />
                  <YAxis 
                    stroke="hsl(var(--muted-foreground))"
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'hsl(var(--card))', 
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '6px'
                    }}
                    labelFormatter={(value) => {
                      const date = new Date(value);
                      return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
                    }}
                  />
                  <Legend 
                    wrapperStyle={{ paddingTop: '20px' }}
                    iconType="line"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="users" 
                    stroke={getComputedColor('--accent')} 
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="Users"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="engagements" 
                    stroke={getComputedColor('--primary')} 
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="Engagements"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="firms" 
                    stroke={getComputedColor('--warning')} 
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="Firms"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="ai_generations" 
                    stroke={getComputedColor('--success')} 
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="AI Generations"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="card-trinity p-6">
          <h3 className="font-heading font-semibold text-lg mb-4">Recent Ai Generation</h3>
          <div className="space-y-4">
            {stats && stats.recent_ai_generations && stats.recent_ai_generations.length > 0 ? (
              stats.recent_ai_generations.map((generation, i) => (
                <div key={i} className="flex items-start gap-3 pb-3 border-b border-border last:border-0 last:pb-0">
                  <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-medium">{generation.user_name.charAt(0).toUpperCase()}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">
                      <span className="font-medium">{generation.user_name}</span>{' '}
                      <span className="text-muted-foreground">completed a diagnostic for {generation.engagement_name}</span>
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">{generation.time_ago}</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-4 text-sm text-muted-foreground">
                No recent AI generations
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function AdvisorDashboard() {
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

function ClientDashboard() {
  const [stats, setStats] = useState<ClientDashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchDashboardStats = async () => {
      try {
        setIsLoading(true);
        setError(null);
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
        setStats(data);
      } catch (err) {
        console.error('Failed to fetch dashboard stats:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch dashboard stats');
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboardStats();
  }, []);

  // Format file size
  const formatFileSize = (bytes: number | null): string => {
    if (!bytes) return 'Unknown size';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Format date
  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      });
    } catch {
      return 'Invalid date';
    }
  };

  // Format task status for display
  const formatTaskStatus = (status: string): string => {
    const statusMap: Record<string, string> = {
      'pending': 'Pending',
      'in_progress': 'In Progress',
      'completed': 'Completed',
      'cancelled': 'Cancelled'
    };
    return statusMap[status] || status;
  };

  // Get status badge class
  const getStatusBadgeClass = (status: string): string => {
    const statusLower = status.toLowerCase();
    if (statusLower === 'completed') return 'status-success';
    if (statusLower === 'in_progress') return 'status-info';
    if (statusLower === 'pending') return 'status-warning';
    if (statusLower === 'cancelled') return 'bg-muted text-muted-foreground';
    return 'bg-muted text-muted-foreground';
  };

  // Calculate pending tasks count
  const pendingTasksCount = stats?.latest_tasks.filter(
    task => task.status === 'pending' || task.status === 'in_progress'
  ).length || 0;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Clock className="w-6 h-6 animate-spin text-accent" />
        <span className="ml-2 text-muted-foreground">Loading dashboard...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-8 h-8 text-destructive mb-4" />
        <p className="text-destructive font-medium mb-2">Failed to load dashboard</p>
        <p className="text-sm text-muted-foreground mb-4">{error}</p>
        <button 
          onClick={() => window.location.reload()} 
          className="btn-primary"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No dashboard data available
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard 
          title="My Tasks" 
          value={stats.total_tasks.toString()} 
          change={pendingTasksCount > 0 ? `${pendingTasksCount} pending` : undefined}
          changeType={pendingTasksCount > 0 ? "negative" : "neutral"}
          icon={CheckSquare}
        />
        <StatCard 
          title="Documents" 
          value={stats.total_documents.toString()} 
          icon={FileText}
        />
        <StatCard 
          title="Diagnostics" 
          value={stats.total_diagnostics.toString()} 
          icon={TrendingUp}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card-trinity p-6">
          <h3 className="font-heading font-semibold text-lg mb-4">Your Tasks</h3>
          <div className="space-y-3">
            {stats.latest_tasks.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <CheckSquare className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No tasks found</p>
              </div>
            ) : (
              stats.latest_tasks.map((task) => (
                <div 
                  key={task.id} 
                  className="flex items-center gap-3 p-4 rounded-lg border border-border hover:border-accent/50 transition-colors cursor-pointer"
                  onClick={() => navigate('/dashboard/tasks')}
                >
                  <input 
                    type="checkbox" 
                    checked={task.status === 'completed'}
                    className="w-5 h-5 rounded border-input accent-accent"
                    readOnly
                  />
                  <div className="flex-1 min-w-0">
                    <p className={cn(
                      "text-sm font-medium",
                      task.status === 'completed' && "line-through text-muted-foreground"
                    )}>{task.title}</p>
                    {task.engagement_name && (
                      <p className="text-xs text-muted-foreground mt-1">{task.engagement_name}</p>
                    )}
                  </div>
                  <span className={cn("status-badge", getStatusBadgeClass(task.status))}>
                    {formatTaskStatus(task.status)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card-trinity p-6">
          <h3 className="font-heading font-semibold text-lg mb-4">Recent Documents</h3>
          <div className="space-y-3">
            {stats.recent_documents.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No documents uploaded yet</p>
              </div>
            ) : (
              stats.recent_documents.map((doc) => (
                <div 
                  key={doc.id} 
                  className="flex items-center gap-3 p-4 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                  onClick={() => navigate('/dashboard/documents')}
                >
                  <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                    <FileText className="w-5 h-5 text-accent" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{doc.file_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(doc.created_at)} • {formatFileSize(doc.file_size)}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* <div className="card-trinity p-6">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center">
            <Brain className="w-6 h-6 text-accent" />
          </div>
          <div>
            <h3 className="font-heading font-semibold text-lg">Trinity AI Assistant</h3>
            <p className="text-sm text-muted-foreground">Get answers about your business using AI</p>
          </div>
        </div>
        <button 
          className="btn-primary"
          onClick={() => navigate('/dashboard/chat')}
        >
          Start a conversation <ArrowRight className="w-4 h-4 ml-2" />
        </button>
      </div> */}
    </div>
  );
}

function AdminDashboard() {
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

function FirmAdminDashboard() {
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

export default function DashboardHome() {
  const { user } = useAuth();

  const getDashboardTitle = () => {
    switch (user?.role) {
      case 'super_admin': return 'Platform Overview';
      case 'admin': return 'Administration Dashboard';
      case 'advisor': return 'Advisor Dashboard';
      case 'client': return 'My Dashboard';
      case 'firm_admin': return 'Firm Dashboard';
      case 'firm_advisor': return 'Advisor Dashboard';
      default: return 'Dashboard';
    }
  };

  const renderDashboard = () => {
    switch (user?.role) {
      case 'super_admin': return <SuperAdminDashboard />;
      case 'admin': return <AdminDashboard />;
      case 'advisor':
      case 'firm_advisor': return <AdvisorDashboard />;
      case 'client': return <ClientDashboard />;
      case 'firm_admin': return <FirmAdminDashboard />;
      default: return null;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">
            {getDashboardTitle()}
          </h1>
          <p className="text-muted-foreground mt-1">
            Welcome back, {user?.name.split(' ')[0]}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="w-4 h-4" />
          Last updated: Just now
        </div>
      </div>

      {renderDashboard()}
    </div>
  );
}
