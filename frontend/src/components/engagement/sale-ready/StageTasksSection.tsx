import { useMemo, useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  createTask,
  updateTask,
  deleteTask,
  fetchTasks,
  type Task,
  type TaskCreatePayload,
  type TaskUpdatePayload,
} from '@/store/slices/tasksReducer';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Plus, CheckSquare, ListTodo, Sparkles } from 'lucide-react';
import { TaskItem } from '@/components/engagement/tasks/TaskItem';
import { TaskForm } from '@/components/engagement/tasks/TaskForm';
import type { LucideIcon } from 'lucide-react';

interface StageTasksSectionProps {
  engagementId: string;
  stageCode: string;
  canEdit?: boolean;
}

// Order and labels for the pre-loaded sections. Custom (advisor-added) tasks are
// tagged 'ai_custom'; tasks with no section fall under Custom too.
const SECTIONS: { key: string; label: string; icon: LucideIcon }[] = [
  { key: 'must_do', label: 'Must-Do', icon: CheckSquare },
  { key: 'optional', label: 'Optional', icon: ListTodo },
  { key: 'ai_custom', label: 'AI / Advisor Custom', icon: Sparkles },
];

export function StageTasksSection({ engagementId, stageCode, canEdit = false }: StageTasksSectionProps) {
  const dispatch = useAppDispatch();
  const allTasks = useAppSelector((state) => state.task.tasks);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);

  const stageTasks = useMemo(
    () => allTasks.filter((t) => t.engagementId === engagementId && t.moduleReference === stageCode),
    [allTasks, engagementId, stageCode],
  );

  const grouped = useMemo(() => {
    const map: Record<string, Task[]> = { must_do: [], optional: [], ai_custom: [] };
    stageTasks.forEach((t) => {
      const key = t.section && map[t.section] ? t.section : 'ai_custom';
      map[key].push(t);
    });
    return map;
  }, [stageTasks]);

  const handleCreate = async (data: TaskCreatePayload) => {
    // Tag custom tasks with the current stage + custom section (reuses the standard flow).
    await dispatch(createTask({ ...data, engagementId, moduleReference: stageCode, section: 'ai_custom' })).unwrap();
    setIsCreateOpen(false);
    dispatch(fetchTasks({ engagementId, limit: 1000 }));
  };

  const handleUpdate = async (taskId: string, updates: TaskUpdatePayload) => {
    await dispatch(updateTask({ id: taskId, updates })).unwrap();
    setEditingTask(null);
    dispatch(fetchTasks({ engagementId, limit: 1000 }));
  };

  const handleDelete = async (taskId: string) => {
    if (!window.confirm('Delete this task?')) return;
    await dispatch(deleteTask(taskId)).unwrap();
    dispatch(fetchTasks({ engagementId, limit: 1000 }));
  };

  return (
    <div className="space-y-5">
      {canEdit && (
        <div className="flex justify-end">
          <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline">
                <Plus className="h-4 w-4 mr-1.5" /> Add custom task
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Add custom task</DialogTitle>
              </DialogHeader>
              <TaskForm engagementId={engagementId} onSubmit={(d) => handleCreate(d as TaskCreatePayload)} onCancel={() => setIsCreateOpen(false)} />
            </DialogContent>
          </Dialog>
        </div>
      )}

      {SECTIONS.map(({ key, label, icon: SectionIcon }) => (
        <div key={key} className="space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <SectionIcon className="h-3.5 w-3.5" />
            <span>{label}</span>
            <Badge variant="secondary" className="rounded-full ml-0.5">{grouped[key].length}</Badge>
          </div>
          {grouped[key].length === 0 ? (
            <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">No {label.toLowerCase()} tasks.</div>
          ) : (
            <div className="space-y-3">
              {grouped[key].map((task) => (
                <TaskItem
                  key={task.id}
                  task={task}
                  onEdit={() => setEditingTask(task)}
                  onDelete={() => handleDelete(task.id)}
                  onStatusChange={(status) => handleUpdate(task.id, { status: status as TaskUpdatePayload['status'] })}
                  onClick={() => setEditingTask(task)}
                />
              ))}
            </div>
          )}
        </div>
      ))}

      {editingTask && (
        <Dialog open={!!editingTask} onOpenChange={(open) => !open && setEditingTask(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Edit Task</DialogTitle>
            </DialogHeader>
            <TaskForm task={editingTask} onSubmit={(updates) => handleUpdate(editingTask.id, updates as TaskUpdatePayload)} onCancel={() => setEditingTask(null)} />
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
