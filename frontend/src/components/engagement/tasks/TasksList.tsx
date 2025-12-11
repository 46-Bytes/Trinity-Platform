import { useEffect, useState, useMemo } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchTasks, createTask, updateTask, deleteTask, setFilters, type Task, type TaskCreatePayload, type TaskUpdatePayload } from '@/store/slices/tasksReducer';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { Plus, Search } from 'lucide-react';
import { TaskForm } from './TaskForm';
import { TaskItem } from './TaskItem';

interface TasksListProps {
  engagementId: string;
}

const TASKS_PER_PAGE = 10;

export function TasksList({ engagementId }: TasksListProps) {
  const dispatch = useAppDispatch();
  const { tasks, isLoading, error, filters } = useAppSelector((state) => state.task);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Filter tasks for this engagement
  const engagementTasks = tasks.filter((task) => task.engagementId === engagementId);

  // Filter tasks by search query
  const filteredTasks = useMemo(() => {
    if (!searchQuery.trim()) {
      return engagementTasks;
    }
    const query = searchQuery.toLowerCase();
    return engagementTasks.filter((task) => {
      const titleMatch = task.title?.toLowerCase().includes(query);
      const descriptionMatch = task.description?.toLowerCase().includes(query);
      const assignedToMatch = task.assignedToName?.toLowerCase().includes(query);
      return titleMatch || descriptionMatch || assignedToMatch;
    });
  }, [engagementTasks, searchQuery]);

  // Calculate pagination
  const totalPages = Math.ceil(filteredTasks.length / TASKS_PER_PAGE);
  const startIndex = (currentPage - 1) * TASKS_PER_PAGE;
  const endIndex = startIndex + TASKS_PER_PAGE;
  const paginatedTasks = filteredTasks.slice(startIndex, endIndex);

  // Reset to page 1 when search or filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, priorityFilter]);

  useEffect(() => {
    // Fetch tasks for this engagement
    dispatch(fetchTasks({ 
      engagementId, 
      status: statusFilter !== 'all' ? statusFilter : undefined, 
      priority: priorityFilter !== 'all' ? priorityFilter : undefined,
      limit: 1000 // Fetch all tasks for this engagement to enable client-side search
    }));
  }, [dispatch, engagementId, statusFilter, priorityFilter]);

  const handleCreateTask = async (taskData: TaskCreatePayload) => {
    try {
      await dispatch(createTask({ ...taskData, engagementId })).unwrap();
      setIsCreateDialogOpen(false);
      // Refresh tasks
      dispatch(fetchTasks({ engagementId }));
    } catch (error) {
      console.error('Failed to create task:', error);
    }
  };

  const handleUpdateTask = async (taskId: string, updates: TaskUpdatePayload) => {
    try {
      await dispatch(updateTask({ id: taskId, updates })).unwrap();
      setEditingTask(null);
      // Refresh tasks
      dispatch(fetchTasks({ engagementId }));
    } catch (error) {
      console.error('Failed to update task:', error);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    if (window.confirm('Are you sure you want to delete this task?')) {
      try {
        await dispatch(deleteTask(taskId)).unwrap();
        // Refresh tasks
        dispatch(fetchTasks({ engagementId }));
      } catch (error) {
        console.error('Failed to delete task:', error);
      }
    }
  };

  const pendingTasks = filteredTasks.filter((t) => t.status === 'pending').length;
  const inProgressTasks = filteredTasks.filter((t) => t.status === 'in_progress').length;
  const completedTasks = filteredTasks.filter((t) => t.status === 'completed').length;

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    // Scroll to top of tasks list
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Pending</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pendingTasks}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">In Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{inProgressTasks}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Completed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{completedTasks}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Actions */}
      <Card>
        <CardHeader>
          <div className="space-y-4">
            {/* Search Bar */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search tasks by title, description, or assignee..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            <div className="flex items-center justify-between">
              <CardTitle>
                Tasks {filteredTasks.length > 0 && `(${filteredTasks.length})`}
              </CardTitle>
              <div className="flex items-center gap-4">
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="Status" />
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
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="Priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Priority</SelectItem>
                    <SelectItem value="urgent">Urgent</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>

                <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="h-4 w-4 mr-2" />
                      New Task
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-2xl">
                    <DialogHeader>
                      <DialogTitle>Create New Task</DialogTitle>
                    </DialogHeader>
                    <TaskForm
                      engagementId={engagementId}
                      onSubmit={handleCreateTask}
                      onCancel={() => setIsCreateDialogOpen(false)}
                    />
                  </DialogContent>
                </Dialog>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading tasks...</div>
          ) : error ? (
            <div className="text-center py-8 text-destructive">{error}</div>
          ) : filteredTasks.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchQuery ? 'No tasks match your search.' : 'No tasks found. Create your first task to get started.'}
            </div>
          ) : (
            <>
              <div className="space-y-4">
                {paginatedTasks.map((task) => (
                  <TaskItem
                    key={task.id}
                    task={task}
                    onEdit={() => setEditingTask(task)}
                    onDelete={() => handleDeleteTask(task.id)}
                    onStatusChange={(newStatus) => handleUpdateTask(task.id, { status: newStatus as any })}
                  />
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="mt-6 flex items-center justify-between">
                  <div className="text-sm text-muted-foreground">
                    Showing {startIndex + 1} to {Math.min(endIndex, filteredTasks.length)} of {filteredTasks.length} tasks
                  </div>
                  <Pagination>
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious
                          href="#"
                          onClick={(e) => {
                            e.preventDefault();
                            if (currentPage > 1) {
                              handlePageChange(currentPage - 1);
                            }
                          }}
                          className={currentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                        />
                      </PaginationItem>
                      
                      {(() => {
                        const pages: (number | 'ellipsis')[] = [];
                        
                        if (totalPages <= 7) {
                          // Show all pages if 7 or fewer
                          for (let i = 1; i <= totalPages; i++) {
                            pages.push(i);
                          }
                        } else {
                          // Always show first page
                          pages.push(1);
                          
                          if (currentPage <= 3) {
                            // Show first 5 pages, then ellipsis, then last
                            for (let i = 2; i <= 5; i++) {
                              pages.push(i);
                            }
                            pages.push('ellipsis');
                            pages.push(totalPages);
                          } else if (currentPage >= totalPages - 2) {
                            // Show first, ellipsis, then last 5 pages
                            pages.push('ellipsis');
                            for (let i = totalPages - 4; i <= totalPages; i++) {
                              pages.push(i);
                            }
                          } else {
                            // Show first, ellipsis, current-1, current, current+1, ellipsis, last
                            pages.push('ellipsis');
                            pages.push(currentPage - 1);
                            pages.push(currentPage);
                            pages.push(currentPage + 1);
                            pages.push('ellipsis');
                            pages.push(totalPages);
                          }
                        }
                        
                        return pages.map((page, index) => {
                          if (page === 'ellipsis') {
                            return (
                              <PaginationItem key={`ellipsis-${index}`}>
                                <span className="px-2">...</span>
                              </PaginationItem>
                            );
                          }
                          return (
                            <PaginationItem key={page}>
                              <PaginationLink
                                href="#"
                                onClick={(e) => {
                                  e.preventDefault();
                                  handlePageChange(page);
                                }}
                                isActive={currentPage === page}
                                className="cursor-pointer"
                              >
                                {page}
                              </PaginationLink>
                            </PaginationItem>
                          );
                        });
                      })()}
                      
                      <PaginationItem>
                        <PaginationNext
                          href="#"
                          onClick={(e) => {
                            e.preventDefault();
                            if (currentPage < totalPages) {
                              handlePageChange(currentPage + 1);
                            }
                          }}
                          className={currentPage === totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                        />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      {editingTask && (
        <Dialog open={!!editingTask} onOpenChange={(open) => !open && setEditingTask(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Edit Task</DialogTitle>
            </DialogHeader>
            <TaskForm
              task={editingTask}
              onSubmit={(updates) => handleUpdateTask(editingTask.id, updates)}
              onCancel={() => setEditingTask(null)}
            />
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

