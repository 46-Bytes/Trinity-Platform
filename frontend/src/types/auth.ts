export type UserRole = 'super_admin' | 'admin' | 'advisor' | 'client' | 'firm_admin' | 'firm_advisor';

export interface User {
  id: string;
  email: string;
  name: string;
  nickname?: string;
  role: UserRole;
  avatar?: string;
  firmId?: string;
  createdAt: string;
  bio?: string;
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
};

export const roleColors: Record<UserRole, string> = {
  super_admin: 'bg-purple-100 text-purple-700',
  admin: 'bg-blue-100 text-blue-700',
  advisor: 'bg-accent/10 text-accent',
  client: 'bg-muted text-muted-foreground',
  firm_admin: 'bg-orange-100 text-orange-700',
  firm_advisor: 'bg-teal-100 text-teal-700',
};
