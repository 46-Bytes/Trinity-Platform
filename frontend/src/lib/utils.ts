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