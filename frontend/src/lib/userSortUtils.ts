import type { User } from '@/store/slices/userReducer';
import type { Advisor } from '@/store/slices/engagementReducer';

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

function normalizeSortValue(value?: string): string {
  return (value || '').trim().toLocaleLowerCase();
}

function getNameFromParts(advisor: Advisor): string {
  const given = (advisor.given_name || '').trim();
  const family = (advisor.family_name || '').trim();
  if (given || family) {
    return `${given} ${family}`.trim();
  }
  return (advisor.name || '').trim();
}

function extractLastToken(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : '';
}

/**
 * Sort advisors alphabetically by surname/last name.
 * Priority:
 * 1) Explicit family_name
 * 2) Last token from display name
 * 3) given_name then full name as deterministic tiebreakers
 */
export function sortAdvisorsBySurname(advisors: Advisor[]): Advisor[] {
  return [...advisors].sort((a, b) => {
    const displayA = getNameFromParts(a);
    const displayB = getNameFromParts(b);

    const surnameA = normalizeSortValue(a.family_name) || normalizeSortValue(extractLastToken(displayA));
    const surnameB = normalizeSortValue(b.family_name) || normalizeSortValue(extractLastToken(displayB));

    const surnameCmp = surnameA.localeCompare(surnameB, undefined, {
      sensitivity: 'base',
      numeric: true,
    });
    if (surnameCmp !== 0) {
      return surnameCmp;
    }

    const givenCmp = normalizeSortValue(a.given_name).localeCompare(normalizeSortValue(b.given_name), undefined, {
      sensitivity: 'base',
      numeric: true,
    });
    if (givenCmp !== 0) {
      return givenCmp;
    }

    const fullNameCmp = normalizeSortValue(displayA).localeCompare(normalizeSortValue(displayB), undefined, {
      sensitivity: 'base',
      numeric: true,
    });
    if (fullNameCmp !== 0) {
      return fullNameCmp;
    }

    return a.id.localeCompare(b.id, undefined, {
      sensitivity: 'base',
      numeric: true,
    });
  });
}

