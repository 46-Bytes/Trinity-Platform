import { useAuth } from '@/context/AuthContext';
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
import { cn } from '@/lib/utils';

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
  const engagements = [
    { client: 'Acme Corp', status: 'Active', progress: 75, tasks: 12, pending: 3 },
    { client: 'TechStart Inc', status: 'Active', progress: 45, tasks: 8, pending: 5 },
    { client: 'Global Solutions', status: 'In Review', progress: 90, tasks: 15, pending: 1 },
    { client: 'Innovate Ltd', status: 'Active', progress: 30, tasks: 6, pending: 4 },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          title="Active Clients" 
          value="12" 
          icon={Users}
        />
        <StatCard 
          title="Open Tasks" 
          value="28" 
          change="8 due this week" 
          changeType="neutral"
          icon={CheckSquare}
        />
        <StatCard 
          title="Documents" 
          value="156" 
          icon={FileText}
        />
        <StatCard 
          title="AI Tools Used" 
          value="42" 
          change="+15 this month" 
          changeType="positive"
          icon={Brain}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card-trinity p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-heading font-semibold text-lg">Client Engagements</h3>
            <button className="btn-trinity text-accent hover:bg-accent/10">
              View all <ArrowRight className="w-4 h-4 ml-1" />
            </button>
          </div>
          <div className="overflow-x-auto">
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
                {engagements.map((eng, i) => (
                  <tr key={i} className="cursor-pointer">
                    <td className="font-medium">{eng.client}</td>
                    <td>
                      <span className={cn(
                        "status-badge",
                        eng.status === 'Active' && "status-success",
                        eng.status === 'In Review' && "status-info"
                      )}>
                        {eng.status}
                      </span>
                    </td>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="progress-trinity w-24">
                          <div className="progress-trinity-bar" style={{ width: `${eng.progress}%` }} />
                        </div>
                        <span className="text-sm text-muted-foreground">{eng.progress}%</span>
                      </div>
                    </td>
                    <td>
                      <span className="text-sm">
                        {eng.tasks} total • <span className="text-warning">{eng.pending} pending</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-6">
          <div className="card-trinity p-6">
            <h3 className="font-heading font-semibold text-lg mb-4">Upcoming Tasks</h3>
            <div className="space-y-3">
              {[
                { title: 'Review diagnostic report', client: 'Acme Corp', due: 'Today' },
                { title: 'Generate business plan', client: 'TechStart', due: 'Tomorrow' },
                { title: 'Client meeting prep', client: 'Global Solutions', due: 'Wed' },
              ].map((task, i) => (
                <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer">
                  <div className={cn(
                    "w-2 h-2 rounded-full flex-shrink-0",
                    task.due === 'Today' ? "bg-warning" : "bg-accent"
                  )} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{task.title}</p>
                    <p className="text-xs text-muted-foreground">{task.client}</p>
                  </div>
                  <span className={cn(
                    "text-xs font-medium",
                    task.due === 'Today' && "text-warning"
                  )}>{task.due}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card-trinity p-6">
            <h3 className="font-heading font-semibold text-lg mb-4">Quick Actions</h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'New Client', icon: Users },
                { label: 'Create Task', icon: CheckSquare },
                { label: 'AI Tools', icon: Brain },
                { label: 'Upload', icon: FileText },
              ].map((action, i) => (
                <button key={i} className="flex flex-col items-center gap-2 p-4 rounded-lg bg-muted/30 hover:bg-accent/10 hover:text-accent transition-all">
                  <action.icon className="w-5 h-5" />
                  <span className="text-xs font-medium">{action.label}</span>
                </button>
              ))}
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
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          title="Total Users" 
          value="156" 
          change="+8 this week" 
          changeType="positive"
          icon={Users}
        />
        <StatCard 
          title="Active Advisors" 
          value="24" 
          icon={Users}
        />
        <StatCard 
          title="Pending Tasks" 
          value="89" 
          icon={CheckSquare}
        />
        <StatCard 
          title="AI Requests" 
          value="1,247" 
          change="+32% this month" 
          changeType="positive"
          icon={Brain}
        />
      </div>

      <div className="card-trinity p-6">
        <h3 className="font-heading font-semibold text-lg mb-4">User Management</h3>
        <p className="text-muted-foreground mb-4">Create and manage user accounts. Note: As an Admin, you cannot view client engagement files.</p>
        <div className="flex gap-3">
          <button className="btn-primary">Create User</button>
          <button className="btn-secondary">Manage Roles</button>
        </div>
      </div>
    </div>
  );
}

function FirmAdminDashboard() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          title="Firm Advisors" 
          value="8" 
          change="2 available seats" 
          changeType="neutral"
          icon={Users}
        />
        <StatCard 
          title="Total Clients" 
          value="45" 
          icon={Users}
        />
        <StatCard 
          title="Active Engagements" 
          value="38" 
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
            {[
              { name: 'Emma Thompson', clients: 12, status: 'Active' },
              { name: 'James Wilson', clients: 8, status: 'Active' },
              { name: 'Lisa Anderson', clients: 15, status: 'Active' },
              { name: 'Mark Davis', clients: 10, status: 'On Leave' },
            ].map((advisor, i) => (
              <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
                <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-medium">
                  {advisor.name.charAt(0)}
                </div>
                <div className="flex-1">
                  <p className="font-medium text-sm">{advisor.name}</p>
                  <p className="text-xs text-muted-foreground">{advisor.clients} clients</p>
                </div>
                <span className={cn(
                  "status-badge",
                  advisor.status === 'Active' ? "status-success" : "status-warning"
                )}>
                  {advisor.status}
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
              <span className="font-medium">8 / 10</span>
            </div>
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
