import { useAuth } from '@/context/AuthContext';
import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchFirm, fetchFirmAdvisors, fetchFirmClients, fetchFirmStats } from '@/store/slices/firmReducer';
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
  Brain
} from 'lucide-react';
import { cn, getUniqueClientIds } from '@/lib/utils';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import { fetchTasks } from '@/store/slices/tasksReducer';
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

// Role-specific dashboard components
function SuperAdminDashboard() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          title="Total Users" 
          value="1,284" 
          change="+12% this month" 
          changeType="positive"
          icon={Users}
        />
        <StatCard 
          title="Active Engagements" 
          value="342" 
          change="+8% this month" 
          changeType="positive"
          icon={FolderOpen}
        />
        <StatCard 
          title="Tasks Completed" 
          value="2,847" 
          change="+23% this month" 
          changeType="positive"
          icon={CheckSquare}
        />
        <StatCard 
          title="AI Generations" 
          value="5,621" 
          change="+45% this month" 
          changeType="positive"
          icon={Brain}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card-trinity p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-heading font-semibold text-lg">Platform Activity</h3>
            <select className="input-trinity py-1.5 px-3 text-sm w-auto">
              <option>Last 7 days</option>
              <option>Last 30 days</option>
              <option>Last 90 days</option>
            </select>
          </div>
          <div className="h-64 flex items-center justify-center bg-muted/30 rounded-lg">
            <p className="text-muted-foreground">Activity chart placeholder</p>
          </div>
        </div>

        <div className="card-trinity p-6">
          <h3 className="font-heading font-semibold text-lg mb-4">Recent Activity</h3>
          <div className="space-y-4">
            {[
              { user: 'Emma Thompson', action: 'created a new engagement', time: '5m ago' },
              { user: 'James Wilson', action: 'generated a business plan', time: '12m ago' },
              { user: 'Lisa Anderson', action: 'completed a diagnostic', time: '25m ago' },
              { user: 'Michael Chen', action: 'uploaded documents', time: '1h ago' },
            ].map((activity, i) => (
              <div key={i} className="flex items-start gap-3 pb-3 border-b border-border last:border-0 last:pb-0">
                <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-medium">{activity.user.charAt(0)}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm">
                    <span className="font-medium">{activity.user}</span>{' '}
                    <span className="text-muted-foreground">{activity.action}</span>
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function AdvisorDashboard() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { engagements, isLoading: engagementsLoading } = useAppSelector((state) => state.engagement);
  const { tasks, isLoading: tasksLoading } = useAppSelector((state) => state.task);
  
  // Fetch data on mount
  useEffect(() => {
    dispatch(fetchEngagements({}));
    dispatch(fetchTasks({ limit: 1000 }));
  }, [dispatch]);
  
  // Calculate real analytics
  const uniqueClients = getUniqueClientIds(engagements).size;
  const totalEngagements = engagements.length;
  const totalDocuments = engagements.reduce((sum, e) => sum + (e.documentsCount || 0), 0);
  const pendingTasks = tasks.filter(t => t.status === 'pending' || t.status === 'in_progress').length;
  
  const isLoading = engagementsLoading || tasksLoading;

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
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard 
          title="My Tasks" 
          value="8" 
          change="3 pending" 
          changeType="neutral"
          icon={CheckSquare}
        />
        <StatCard 
          title="Documents" 
          value="24" 
          icon={FileText}
        />
        <StatCard 
          title="Diagnostics" 
          value="3" 
          change="1 to complete" 
          changeType="neutral"
          icon={TrendingUp}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card-trinity p-6">
          <h3 className="font-heading font-semibold text-lg mb-4">Your Tasks</h3>
          <div className="space-y-3">
            {[
              { title: 'Complete financial diagnostic', status: 'In Progress', priority: 'high' },
              { title: 'Review business plan draft', status: 'Pending', priority: 'medium' },
              { title: 'Upload annual reports', status: 'Not Started', priority: 'low' },
              { title: 'Schedule strategy session', status: 'Completed', priority: 'medium' },
            ].map((task, i) => (
              <div key={i} className="flex items-center gap-3 p-4 rounded-lg border border-border hover:border-accent/50 transition-colors cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={task.status === 'Completed'}
                  className="w-5 h-5 rounded border-input accent-accent"
                  readOnly
                />
                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-sm font-medium",
                    task.status === 'Completed' && "line-through text-muted-foreground"
                  )}>{task.title}</p>
                </div>
                <span className={cn(
                  "status-badge",
                  task.status === 'Completed' && "status-success",
                  task.status === 'In Progress' && "status-info",
                  task.status === 'Pending' && "status-warning",
                  task.status === 'Not Started' && "bg-muted text-muted-foreground"
                )}>
                  {task.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="card-trinity p-6">
          <h3 className="font-heading font-semibold text-lg mb-4">Recent Documents</h3>
          <div className="space-y-3">
            {[
              { name: 'Business Plan v2.pdf', date: 'Dec 1, 2024', size: '2.4 MB' },
              { name: 'Financial Analysis.xlsx', date: 'Nov 28, 2024', size: '1.1 MB' },
              { name: 'Strategy Presentation.pptx', date: 'Nov 25, 2024', size: '5.2 MB' },
            ].map((doc, i) => (
              <div key={i} className="flex items-center gap-3 p-4 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer">
                <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-accent" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{doc.name}</p>
                  <p className="text-xs text-muted-foreground">{doc.date} • {doc.size}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card-trinity p-6">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center">
            <Brain className="w-6 h-6 text-accent" />
          </div>
          <div>
            <h3 className="font-heading font-semibold text-lg">Trinity AI Assistant</h3>
            <p className="text-sm text-muted-foreground">Get answers about your business using AI</p>
          </div>
        </div>
        <button className="btn-primary">
          Start a conversation <ArrowRight className="w-4 h-4 ml-2" />
        </button>
      </div>
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
          title="Monthly Usage" 
          value="$2,450" 
          icon={TrendingUp}
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
