import { useState, useEffect } from 'react';
import { StatCard } from '@/components/ui/stat-card';
import { 
  Users, 
  FolderOpen, 
  CheckSquare, 
  Brain,
  Clock,
  AlertCircle
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

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

interface ActivityDataPoint {
  date: string;
  users: number;
  engagements: number;
  firms: number;
  ai_generations: number;
}

export function SuperAdminDashboard() {
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
            <Select value={String(timePeriod)} onValueChange={(v) => setTimePeriod(Number(v))}>
              <SelectTrigger className="h-9 w-[140px] bg-background">
                <SelectValue placeholder="Time period" />
              </SelectTrigger>
              <SelectContent align="end">
                <SelectItem value="7">Last 7 days</SelectItem>
                <SelectItem value="30">Last 30 days</SelectItem>
                <SelectItem value="90">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
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

