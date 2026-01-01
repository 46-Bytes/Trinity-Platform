import type { Task } from '@/store/slices/tasksReducer';

/**
 * Status priority order for sorting tasks:
 * 1. pending
 * 2. in_progress
 * 3. completed
 * 4. cancelled
 */
const STATUS_PRIORITY: Record<string, number> = {
  'pending': 1,
  'in_progress': 2,
  'completed': 3,
  'cancelled': 4,
};

/**
 * Sorts tasks by status in the following order:
 * 1. pending
 * 2. in_progress
 * 3. completed
 * 4. cancelled
 * 
 * Tasks with the same status maintain their original order.
 * 
 * @param tasks - Array of tasks to sort
 * @returns Sorted array of tasks
 */
export function sortTasksByStatus(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    const priorityA = STATUS_PRIORITY[a.status] || 999;
    const priorityB = STATUS_PRIORITY[b.status] || 999;
    return priorityA - priorityB;
  });
}

