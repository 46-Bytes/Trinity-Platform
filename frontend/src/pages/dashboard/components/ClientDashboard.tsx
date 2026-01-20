import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { StatCard } from '@/components/ui/stat-card';
import { 
  CheckSquare, 
  FileText, 
  TrendingUp,
  Clock,
  AlertCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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

export function ClientDashboard() {
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

  const pendingTasksCount = stats?.latest_tasks.filter(
    (task) => task.status === 'pending'
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
    </div>
  );
}

