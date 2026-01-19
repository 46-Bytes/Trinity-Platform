import type { User } from '@/store/slices/userReducer';

/**
 * Sorts users by most recently edited/added first.
 * Uses updated_at if available, otherwise falls back to created_at.
 * Most recent timestamps appear first (descending order).
 * 
 * @param users - Array of users to sort
 * @returns Sorted array of users (most recent first)
 */
export function sortUsersByLastEdited(users: User[]): User[] {
  return [...users].sort((a, b) => {
    // Get the most relevant timestamp for each user (updated_at preferred, fallback to created_at)
    const timestampA = a.updated_at || a.created_at;
    const timestampB = b.updated_at || b.created_at;
    
    // Parse timestamps to Date objects for comparison
    const dateA = new Date(timestampA).getTime();
    const dateB = new Date(timestampB).getTime();
    
    // Sort in descending order (most recent first)
    return dateB - dateA;
  });
}

