export type UserRole = 'super_admin' | 'admin' | 'advisor' | 'client' | 'firm_admin' | 'firm_advisor' | 'team_member';

/**
 * How a client account was provisioned.
 *
 * A self-service business owner IS a `client` - same role, same permissions on
 * the engagement surface. `accountType` is what gates the owner-only extras:
 * checkout, billing and team management.
 */
export type AccountType = 'advisory' | 'self_service';

export interface User {
  id: string;
  email: string;
  name: string;
  nickname?: string;
  role: UserRole;
  accountType?: AccountType;
  isSelfService?: boolean;
  businessName?: string;
  avatar?: string;
  firmId?: string;
  createdAt: string;
  updatedAt?: string;
  bio?: string;
  auth0Id?: string; // Auth0 user ID - if present, user is managed by Auth0
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export const roleLabels: Record<UserRole, string> = {
  super_admin: 'Super Admin',
  admin: 'Admin',
  advisor: 'Advisor',
  client: 'Client',
  firm_admin: 'Firm Admin',
  firm_advisor: 'Firm Advisor',
  team_member: 'Team Member',
};

export const roleColors: Record<UserRole, string> = {
  super_admin: 'bg-purple-100 text-purple-700',
  admin: 'bg-blue-100 text-blue-700',
  advisor: 'bg-accent/10 text-accent',
  client: 'bg-muted text-muted-foreground',
  firm_admin: 'bg-orange-100 text-orange-700',
  firm_advisor: 'bg-teal-100 text-teal-700',
  team_member: 'bg-slate-100 text-slate-700',
};

/** True for a self-service business owner (the account holder, not a team member). */
export function isBusinessOwner(user: Pick<User, 'role' | 'isSelfService'> | null | undefined): boolean {
  return !!user && user.role === 'client' && !!user.isSelfService;
}

/** Label shown instead of the raw role for self-service owners. */
export function displayRoleLabel(user: Pick<User, 'role' | 'isSelfService'> | null | undefined): string {
  if (!user) return '';
  if (isBusinessOwner(user)) return 'Business Owner';
  return roleLabels[user.role] ?? user.role;
}
