import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Capitalizes the first letter of each word in a string.
 * Replaces underscores with spaces and handles multiple words.
 * @param str - The string to capitalize
 * @returns The capitalized string
 * @example

 */
export function capitalizeFirstLetter(str: string): string {
  if (!str) return str;
  return str
    .replace(/_/g, ' ')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Gets unique client IDs from an array of engagements.
 * @param engagements - Array of engagements with clientId property
 * @returns Set of unique client IDs
 */
export function getUniqueClientIds(engagements: Array<{ clientId: string }>): Set<string> {
  return new Set(engagements.map(e => e.clientId));
}

/**
 * Gets the className for priority badges based on priority level.
 * @param priority - The priority level (critical, high, medium, low)
 * @returns Tailwind CSS classes for the priority badge
 */
export function getPriorityBadgeClassName(priority: string): string {
  switch (priority) {
    case 'critical':
      return 'border-transparent bg-red-500 text-white hover:bg-red-600';
    case 'high':
      return 'border-transparent bg-orange-500 text-white hover:bg-orange-600';
    case 'medium':
      return 'border-transparent bg-yellow-500 text-white hover:bg-yellow-600';
    case 'low':
      return 'border-transparent bg-gray-500 text-white hover:bg-gray-600';
    default:
      return 'border-transparent bg-gray-500 text-white hover:bg-gray-600';
  }
}

/**
 * Checks if a role is an admin role (admin, firm_admin, or super_admin).
 * @param role - The role string to check
 * @returns True if the role is an admin role, false otherwise
 */
export function isAdminRole(role: string | null | undefined): boolean {
  if (!role) return false;
  const normalizedRole = role.toLowerCase().trim();
  return normalizedRole === 'admin' || normalizedRole === 'firm_admin' || normalizedRole === 'super_admin';
}

/**
 * Formats a role string for display (e.g., 'firm_admin' -> 'Firm Admin', 'super_admin' -> 'Super Admin').
 * @param role - The role string to format
 * @returns The formatted role string, or the original string if formatting fails
 */
export function formatRoleForDisplay(role: string | null | undefined): string {
  if (!role) return '';
  return capitalizeFirstLetter(role);
}

const AUD_FULL = new Intl.NumberFormat('en-AU', {
  style: 'currency',
  currency: 'AUD',
  maximumFractionDigits: 0,
});

const AUD_COMPACT = new Intl.NumberFormat('en-AU', {
  style: 'currency',
  currency: 'AUD',
  notation: 'compact',
  maximumFractionDigits: 1,
});

/**
 * Formats a number as whole AUD (e.g. 2610000 -> "$2,610,000").
 * @param value - The amount in Australian dollars
 * @returns The formatted currency string
 */
export function formatAUD(value: number): string {
  return AUD_FULL.format(value);
}

/**
 * Formats a number as compact AUD for axis ticks and tight tiles (e.g. 2610000 -> "$2.6M").
 * @param value - The amount in Australian dollars
 * @returns The formatted compact currency string
 */
export function formatAUDCompact(value: number): string {
  return AUD_COMPACT.format(value);
}

/**
 * Formats a signed AUD delta with an explicit leading sign (e.g. -50000 -> "-$50,000").
 * @param value - The signed amount in Australian dollars
 * @returns The formatted currency string prefixed with + or -
 */
export function formatAUDDelta(value: number): string {
  return `${value < 0 ? '-' : '+'}${AUD_FULL.format(Math.abs(value))}`;
}

/**
 * Gets initials from a full name (e.g. "Saadullah Khan" -> "SK").
 * @param name - The full name to derive initials from
 * @returns Up to 2 uppercase initials, or "?" if no name is given
 */
export function getInitials(name?: string | null): string {
  const words = name?.trim().split(/\s+/).filter(Boolean) ?? [];
  if (words.length === 0) return '?';
  const initials = words.length === 1 ? words[0].slice(0, 2) : words[0][0] + words[1][0];
  return initials.toUpperCase();
}