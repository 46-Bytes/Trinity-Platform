import type { Task } from '@/store/slices/tasksReducer';



/**
 * @param tasks - Array of tasks to sort
 * @returns Sorted array of tasks with most recently updated first
 */
export function sortTasksByUpdatedAt(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    const dateA = new Date(a.updatedAt).getTime();
    const dateB = new Date(b.updatedAt).getTime();
    return dateB - dateA; // Descending order (newest first)
  });
}

