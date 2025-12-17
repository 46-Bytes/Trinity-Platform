import { useState, useEffect } from 'react';
import { Search, Plus, Calendar, User, AlertCircle, CheckCircle2, Clock, Circle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchTasks, Task } from '@/store/slices/tasksReducer';
import { useNavigate } from 'react-router-dom';

type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled';

const statusConfig: Record<TaskStatus, { label: string; icon: typeof Circle; color: string }> = {
  'pending': { label: 'Pending', icon: Circle, color: 'text-muted-foreground' },
  'in_progress': { label: 'In Progress', icon: Clock, color: 'text-info' },
  'completed': { label: 'Completed', icon: CheckCircle2, color: 'text-success' },
  'cancelled': { label: 'Cancelled', icon: AlertCircle, color: 'text-muted-foreground' },
};

// Map backend task to display format
function mapTaskToDisplay(task: Task) {
  return {
    id: task.id,
    title: task.title,
    description: task.description || '',
    engagementName: task.engagementName || 'Unknown Engagement',
    assignedToName: task.assignedToName || task.createdByName || 'Unassigned',
    dueDate: task.dueDate ? new Date(task.dueDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'No due date',
    status: task.status as TaskStatus,
    priority: task.priority,
    taskType: task.taskType,
  };
}

export default function TasksPage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { tasks, isLoading, error } = useAppSelector((state) => state.task);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState('all');

  // Fetch all tasks for the current user on mount
  useEffect(() => {
    dispatch(fetchTasks({ limit: 1000 })); // Fetch all tasks
  }, [dispatch]);

  // Map tasks to display format
  const displayTasks = tasks.map(mapTaskToDisplay);

  // Filter tasks
  const filteredTasks = displayTasks.filter(task => {
    const matchesSearch = task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.engagementName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || task.status === statusFilter;
    const matchesPriority = priorityFilter === 'all' || task.priority === priorityFilter;
    return matchesSearch && matchesStatus && matchesPriority;
  });

  const tasksByStatus = {
    'pending': filteredTasks.filter(t => t.status === 'pending'),
    'in_progress': filteredTasks.filter(t => t.status === 'in_progress'),
    'completed': filteredTasks.filter(t => t.status === 'completed'),
    'cancelled': filteredTasks.filter(t => t.status === 'cancelled'),
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
          <option value="pending">Pending</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select 
          className="input-trinity w-full sm:w-40"
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
        >
          <option value="all">All Priority</option>
          <option value="urgent">Urgent</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
          <span className="ml-2 text-muted-foreground">Loading tasks...</span>
        </div>
      )}

      {error && !isLoading && (
        <div className="text-center py-12">
          <p className="text-destructive mb-2">Error loading tasks</p>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      )}

      {!isLoading && !error && (
        <>
          {/* Kanban Board View */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {(Object.keys(tasksByStatus) as TaskStatus[]).map((status) => {
              const config = statusConfig[status];
              const statusTasks = tasksByStatus[status];
              
              return (
                <div key={status} className="space-y-3">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-2">
                      <config.icon className={cn("w-4 h-4", config.color)} />
                      <span className="font-medium text-sm">{config.label}</span>
                    </div>
                    <span className="text-sm text-muted-foreground">{statusTasks.length}</span>
                  </div>

                  <div className="space-y-3">
                    {statusTasks.map((task) => (
                      <div 
                        key={task.id}
                        className="card-trinity p-4 cursor-pointer hover:shadow-trinity-md transition-all"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            {task.taskType === 'diagnostic_generated' && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-accent/10 text-accent">AI</span>
                            )}
                            <span className={cn(
                              "px-1.5 py-0.5 rounded text-[10px] font-medium",
                              (task.priority === 'urgent' || task.priority === 'high') && "bg-destructive/10 text-destructive",
                              task.priority === 'medium' && "bg-warning/10 text-warning",
                              task.priority === 'low' && "bg-muted text-muted-foreground"
                            )}>
                              {task.priority}
                            </span>
                          </div>
                        </div>
                        
                        <h4 className="font-medium text-sm mb-1">{task.title}</h4>
                        {task.description && (
                          <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{task.description}</p>
                        )}
                        
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {task.assignedToName.split(' ')[0]}
                          </span>
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {task.dueDate}
                          </span>
                        </div>
                        
                        <div className="mt-2 pt-2 border-t border-border">
                          <span className="text-xs text-muted-foreground">{task.engagementName}</span>
                        </div>
                      </div>
                    ))}

                    {statusTasks.length === 0 && (
                      <div className="p-4 text-center text-sm text-muted-foreground border border-dashed border-border rounded-lg">
                        No tasks
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
