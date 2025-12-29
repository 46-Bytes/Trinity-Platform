import { useState, useEffect } from 'react';
import { Search, Calendar, User, AlertCircle, CheckCircle2, Clock, Circle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchTasks, updateTask, Task, TaskUpdatePayload } from '@/store/slices/tasksReducer';
import { useNavigate } from 'react-router-dom';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { TaskForm } from '@/components/engagement/tasks/TaskForm';

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
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [editingTask, setEditingTask] = useState<Task | null>(null);

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

  const handleUpdateTask = async (taskId: string, updates: TaskUpdatePayload) => {
    try {
      await dispatch(updateTask({ id: taskId, updates })).unwrap();
      if (selectedTask && selectedTask.id === taskId) {
        setSelectedTask({ ...selectedTask, ...updates } as Task);
      }
      // Refresh tasks
      dispatch(fetchTasks({ limit: 1000 }));
    } catch (error) {
      console.error('Failed to update task:', error);
    }
  };

  const getPriorityBadgeVariant = (priority: string) => {
    switch (priority) {
      case 'critical':
        return 'destructive';
      case 'high':
        return 'default';
      case 'medium':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'pending':
        return 'Pending';
      case 'in_progress':
        return 'In Progress';
      case 'completed':
        return 'Completed';
      case 'cancelled':
        return 'Cancelled';
      default:
        return status;
    }
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'completed':
        return 'default';
      case 'in_progress':
        return 'secondary';
      case 'cancelled':
        return 'outline';
      case 'pending':
      default:
        return 'outline';
    }
  };

  // Find the full task object from tasks array
  const getFullTask = (taskId: string): Task | null => {
    return tasks.find(t => t.id === taskId) || null;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Tasks</h1>
          <p className="text-muted-foreground mt-1">Manage and track all your tasks</p>
        </div>
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
        <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as TaskStatus | 'all')}>
          <SelectTrigger className="w-full sm:w-[180px]">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
          </SelectContent>
        </Select>
        <Select value={priorityFilter} onValueChange={setPriorityFilter}>
          <SelectTrigger className="w-full sm:w-[180px]">
            <SelectValue placeholder="All Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Priority</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>
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
                        onClick={() => {
                          const fullTask = getFullTask(task.id);
                          if (fullTask) {
                            setSelectedTask(fullTask);
                          }
                        }}
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

      {/* Task Detail Dialog */}
      {selectedTask && (
        <Dialog open={!!selectedTask} onOpenChange={(open) => !open && setSelectedTask(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Task Details</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <h3 className="font-semibold text-lg mb-2">{selectedTask.title}</h3>
                {selectedTask.description && (
                  <p className="text-sm text-muted-foreground mb-4 whitespace-pre-wrap">{selectedTask.description}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Status</label>
                  <div className="mt-1">
                    <Badge variant={getStatusBadgeVariant(selectedTask.status)}>
                      {getStatusLabel(selectedTask.status)}
                    </Badge>
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-muted-foreground">Priority</label>
                  <div className="mt-1">
                    <Badge variant={getPriorityBadgeVariant(selectedTask.priority)}>
                      {selectedTask.priority}
                    </Badge>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                {selectedTask.assignedToName && (
                  <div>
                    <span className="text-muted-foreground">Assigned to:</span>
                    <span className="ml-2">{selectedTask.assignedToName}</span>
                  </div>
                )}
                {selectedTask.createdByName && (
                  <div>
                    <span className="text-muted-foreground">Created by:</span>
                    <span className="ml-2">{selectedTask.createdByName}</span>
                  </div>
                )}
                {selectedTask.dueDate && (
                  <div>
                    <span className="text-muted-foreground">Due date:</span>
                    <span className="ml-2">
                      {new Date(selectedTask.dueDate).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })}
                    </span>
                  </div>
                )}
                {selectedTask.engagementName && (
                  <div>
                    <span className="text-muted-foreground">Engagement:</span>
                    <span className="ml-2">{selectedTask.engagementName}</span>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-4 border-t">
                <Button variant="outline" onClick={() => setSelectedTask(null)}>
                  Close
                </Button>
                <Button variant="outline" onClick={() => {
                  setSelectedTask(null);
                  setEditingTask(selectedTask);
                }}>
                  Edit Task
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Edit Dialog */}
      {editingTask && (
        <Dialog open={!!editingTask} onOpenChange={(open) => !open && setEditingTask(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Edit Task</DialogTitle>
            </DialogHeader>
            <TaskForm
              task={editingTask}
              onSubmit={(updates) => {
                handleUpdateTask(editingTask.id, updates);
                setEditingTask(null)
              }}
              onCancel={() => setEditingTask(null)}
            />
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
