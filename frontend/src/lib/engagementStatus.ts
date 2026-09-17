/**
 * Engagement lifecycle status: display labels, badge styling and who may change
 * it. Mirrors backend/app/services/engagement_status.py - if the permission rule
 * changes there (it is pending client confirmation), change it here too.
 */
import type { Engagement, EngagementStatus, SettableEngagementStatus } from '@/store/slices/engagementReducer';

export const ENGAGEMENT_STATUS_LABELS: Record<EngagementStatus, string> = {
  draft: 'Draft',
  active: 'Active',
  paused: 'Paused',
  ended: 'Ended',
  completed: 'Completed',
  archived: 'Archived',
};

export const ENGAGEMENT_STATUS_BADGE_CLASSES: Record<EngagementStatus, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  active: 'status-success',
  paused: 'bg-amber-100 text-amber-800',
  ended: 'bg-slate-200 text-slate-700',
  completed: 'bg-muted text-muted-foreground',
  archived: 'bg-muted text-muted-foreground',
};

export function formatEngagementStatus(status: string): string {
  return ENGAGEMENT_STATUS_LABELS[status as EngagementStatus] || status;
}

export function engagementStatusBadgeClass(status: string): string {
  return ENGAGEMENT_STATUS_BADGE_CLASSES[status as EngagementStatus] || 'text-foreground';
}

/** Paused/ended engagements have their tasks hidden from the Tasks views. */
export function isEngagementOnHold(status: string): boolean {
  return status === 'paused' || status === 'ended';
}

// Roles that may change status on any engagement they can see.
const STATUS_CHANGE_ROLES_ANY_ENGAGEMENT = ['admin', 'super_admin'];
// Roles that may change status only on engagements they are assigned to.
const STATUS_CHANGE_ROLES_IF_ASSIGNED = ['advisor', 'firm_advisor'];

export function canChangeEngagementStatus(
  engagement: Pick<Engagement, 'primaryAdvisorId' | 'assignedUsers'>,
  user?: { id?: string; role?: string } | null
): boolean {
  if (!user?.role) return false;
  if (STATUS_CHANGE_ROLES_ANY_ENGAGEMENT.includes(user.role)) return true;
  if (STATUS_CHANGE_ROLES_IF_ASSIGNED.includes(user.role)) {
    if (!user.id) return false;
    if (engagement.primaryAdvisorId === user.id) return true;
    return (engagement.assignedUsers || []).includes(user.id);
  }
  return false;
}

/** The lifecycle actions available from a given status, in display order. */
export function availableStatusActions(
  status: string
): Array<{ target: SettableEngagementStatus; label: string }> {
  if (isEngagementOnHold(status)) {
    return [{ target: 'active', label: 'Recommence' }];
  }
  return [
    { target: 'paused', label: 'Pause' },
    // End hidden for now. Backend, dialog copy and Recommence-from-ended all
    // stay in place - re-enable by uncommenting this line.
    // { target: 'ended', label: 'End' },
  ];
}
