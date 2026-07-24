/**
 * API client for the self-service (SaaS) tier.
 *
 * Covers the business owner funnel - plan catalogue, signup intent, checkout,
 * billing and team management.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export type Program = 'value_builder' | 'sale_ready';
export type TeamAccessLevel = 'collaborator' | 'viewer';
export type TeamMemberStatus = 'invited' | 'active' | 'revoked';

export interface Plan {
  program: Program;
  plan_name: string;
  label: string;
  description: string;
  monthly_price: number;
  currency: string;
  seat_count: number;
  team_member_limit: number;
  features: string[];
}

export interface ProgramsResponse {
  plans: Plan[];
  signup_enabled: boolean;
}

export interface SignupIntentResponse {
  intent_id: string | null;
  redirect_url: string;
  already_registered: boolean;
}

export interface Seats {
  total: number;
  team_member_limit: number;
  team_members_used: number;
}

export interface SubscriptionSummary {
  id: string;
  plan_name: string;
  status: string;
  program: Program | null;
  seat_count: number;
  monthly_price: number | null;
  provider: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean | null;
  cancelled_at: string | null;
}

export interface Account {
  is_self_service: boolean;
  subscription: SubscriptionSummary | null;
  program: Program | null;
  program_label: string | null;
  engagement_id: string | null;
  diagnostic_id: string | null;
  diagnostic_status: string | null;
  seats: Seats;
}

export interface CheckoutResponse {
  redirect_url: string;
  subscription_id: string;
  activated_immediately: boolean;
  engagement_id: string | null;
}

export interface TeamMember {
  id: string;
  member_user_id: string;
  email: string;
  name: string | null;
  access_level: TeamAccessLevel;
  status: TeamMemberStatus;
  is_active: boolean;
  email_verified: boolean;
  invited_at: string | null;
  accepted_at: string | null;
}

export interface TeamListResponse {
  members: TeamMember[];
  seats: Seats;
}

/** Error carrying the HTTP status, so callers can tell 402 (pay up) from 403 (forbidden). */
export class SelfServiceApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = 'SelfServiceApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch(`${API_BASE_URL}/api/self-service${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new SelfServiceApiError(
      body.detail || `Request failed with status ${response.status}`,
      response.status,
    );
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/** Plan catalogue. Public - no token needed. */
export const getPrograms = () => request<ProgramsResponse>('/programs');

/** Park signup details and get the Auth0 redirect. Public. */
export const createSignupIntent = (payload: {
  email: string;
  program: Program;
  name?: string;
  business_name?: string;
}) => request<SignupIntentResponse>('/signup-intent', {
  method: 'POST',
  body: JSON.stringify(payload),
});

/** Start payment for a program. */
export const createCheckout = (program: Program) =>
  request<CheckoutResponse>('/checkout', {
    method: 'POST',
    body: JSON.stringify({ program }),
  });

/** Subscription, program and workspace state for the signed-in owner. */
export const getAccount = () => request<Account>('/account');

export const getBillingPortal = () =>
  request<{ redirect_url: string }>('/billing/portal', { method: 'POST' });

export const cancelSubscription = (atPeriodEnd = true) =>
  request<Account>('/billing/cancel', {
    method: 'POST',
    body: JSON.stringify({ at_period_end: atPeriodEnd }),
  });

export const getTeam = () => request<TeamListResponse>('/team');

export const inviteTeamMember = (payload: {
  email: string;
  name?: string;
  access_level: TeamAccessLevel;
}) => request<TeamMember>('/team/invite', {
  method: 'POST',
  body: JSON.stringify(payload),
});

export const updateTeamMember = (memberId: string, accessLevel: TeamAccessLevel) =>
  request<TeamMember>(`/team/${memberId}`, {
    method: 'PATCH',
    body: JSON.stringify({ access_level: accessLevel }),
  });

export const revokeTeamMember = (memberId: string) =>
  request<void>(`/team/${memberId}`, { method: 'DELETE' });

/** Absolute URL for a backend redirect path returned by the API. */
export const toBackendUrl = (path: string) =>
  path.startsWith('http') ? path : `${API_BASE_URL}${path}`;

export const ACCESS_LEVEL_LABELS: Record<TeamAccessLevel, string> = {
  collaborator: 'Collaborator',
  viewer: 'Viewer',
};

export const ACCESS_LEVEL_DESCRIPTIONS: Record<TeamAccessLevel, string> = {
  collaborator: 'Can complete tasks assigned to them and upload documents.',
  viewer: 'Read-only access to their assigned tasks and shared documents.',
};
