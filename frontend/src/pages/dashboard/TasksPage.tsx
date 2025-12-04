import { useState } from 'react';
import { Search, Plus, Filter, Calendar, User, AlertCircle, CheckCircle2, Clock, Circle } from 'lucide-react';
import { cn } from '@/lib/utils';

type TaskStatus = 'not-started' | 'in-progress' | 'in-review' | 'completed';

interface Task {
  id: string;
  title: string;
  description: string;
  client: string;
  owner: string;
  dueDate: string;
  status: TaskStatus;
  priority: 'low' | 'medium' | 'high';
  source: 'ai' | 'manual';
}

const mockTasks: Task[] = [
  { id: '1', title: 'Complete financial diagnostic', description: 'Review and complete the Q4 financial diagnostic questionnaire', client: 'Acme Corp', owner: 'Michael Chen', dueDate: 'Dec 5, 2024', status: 'in-progress', priority: 'high', source: 'ai' },
  { id: '2', title: 'Review business plan draft', description: 'Review the AI-generated business plan and provide feedback', client: 'TechStart', owner: 'Emma Thompson', dueDate: 'Dec 8, 2024', status: 'not-started', priority: 'medium', source: 'ai' },
  { id: '3', title: 'Upload annual reports', description: 'Upload the last 3 years of annual reports for analysis', client: 'Global Solutions', owner: 'Sarah Johnson', dueDate: 'Dec 10, 2024', status: 'not-started', priority: 'low', source: 'manual' },
  { id: '4', title: 'Schedule strategy session', description: 'Coordinate with team to schedule Q1 strategy planning session', client: 'Innovate Ltd', owner: 'Emma Thompson', dueDate: 'Dec 3, 2024', status: 'in-review', priority: 'medium', source: 'manual' },
  { id: '5', title: 'Generate KPI report', description: 'Use AI tools to generate quarterly KPI performance report', client: 'Pacific Traders', owner: 'Lisa Anderson', dueDate: 'Dec 1, 2024', status: 'completed', priority: 'high', source: 'ai' },
  { id: '6', title: 'Prepare client presentation', description: 'Create presentation slides for upcoming client meeting', client: 'Acme Corp', owner: 'James Wilson', dueDate: 'Dec 12, 2024', status: 'in-progress', priority: 'high', source: 'manual' },
];

const statusConfig: Record<TaskStatus, { label: string; icon: typeof Circle; color: string }> = {
  'not-started': { label: 'Not Started', icon: Circle, color: 'text-muted-foreground' },
  'in-progress': { label: 'In Progress', icon: Clock, color: 'text-info' },
  'in-review': { label: 'In Review', icon: AlertCircle, color: 'text-warning' },
  'completed': { label: 'Completed', icon: CheckCircle2, color: 'text-success' },
};

export default function TasksPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState('all');

  const filteredTasks = mockTasks.filter(task => {
    const matchesSearch = task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.client.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || task.status === statusFilter;
    const matchesPriority = priorityFilter === 'all' || task.priority === priorityFilter;
    return matchesSearch && matchesStatus && matchesPriority;
  });

  const tasksByStatus = {
    'not-started': filteredTasks.filter(t => t.status === 'not-started'),
    'in-progress': filteredTasks.filter(t => t.status === 'in-progress'),
    'in-review': filteredTasks.filter(t => t.status === 'in-review'),
    'completed': filteredTasks.filter(t => t.status === 'completed'),
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Tasks</h1>
          <p className="text-muted-foreground mt-1">Manage and track all your tasks</p>
        </div>
        <button className="btn-primary">
          <Plus className="w-4 h-4" />
          Add Task
        </button>
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-trinity pl-10 w-full"
          />
        </div>
        <select 
          className="input-trinity w-full sm:w-40"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as TaskStatus | 'all')}
        >
          <option value="all">All Status</option>
          <option value="not-started">Not Started</option>
          <option value="in-progress">In Progress</option>
          <option value="in-review">In Review</option>
          <option value="completed">Completed</option>
        </select>
        <select 
          className="input-trinity w-full sm:w-40"
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
        >
          <option value="all">All Priority</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Kanban Board View */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {(Object.keys(tasksByStatus) as TaskStatus[]).map((status) => {
          const config = statusConfig[status];
          const tasks = tasksByStatus[status];
          
          return (
            <div key={status} className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2">
                  <config.icon className={cn("w-4 h-4", config.color)} />
                  <span className="font-medium text-sm">{config.label}</span>
                </div>
                <span className="text-sm text-muted-foreground">{tasks.length}</span>
              </div>

              <div className="space-y-3">
                {tasks.map((task) => (
                  <div 
                    key={task.id}
                    className="card-trinity p-4 cursor-pointer hover:shadow-trinity-md"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        {task.source === 'ai' && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-accent/10 text-accent">AI</span>
                        )}
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] font-medium",
                          task.priority === 'high' && "bg-destructive/10 text-destructive",
                          task.priority === 'medium' && "bg-warning/10 text-warning",
                          task.priority === 'low' && "bg-muted text-muted-foreground"
                        )}>
                          {task.priority}
                        </span>
                      </div>
                    </div>
                    
                    <h4 className="font-medium text-sm mb-1">{task.title}</h4>
                    <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{task.description}</p>
                    
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <User className="w-3 h-3" />
                        {task.owner.split(' ')[0]}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {task.dueDate.split(',')[0]}
                      </span>
                    </div>
                    
                    <div className="mt-2 pt-2 border-t border-border">
                      <span className="text-xs text-muted-foreground">{task.client}</span>
                    </div>
                  </div>
                ))}

                {tasks.length === 0 && (
                  <div className="p-4 text-center text-sm text-muted-foreground border border-dashed border-border rounded-lg">
                    No tasks
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
