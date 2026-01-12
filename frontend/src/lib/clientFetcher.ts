import { Engagement } from '@/store/slices/engagementReducer';
import { User } from '@/context/AuthContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface Client {
  id: string;
  name: string;
  email: string;
  industry: string;
  status: 'Active' | 'Pending';
  engagements: number;
  is_active: boolean;
  email_verified: boolean;
  role?: string;
  contact?: string;
  phone?: string;
}

/**
 * Fetches clients for firm_advisor role based on engagements only
 * (does not check adv_client table)
 * 
 * For firm_advisor, we need to check engagements where they are:
 * - primary_advisor_id matches currentUserId, OR
 * - secondary_advisor_ids array includes currentUserId
 */
export async function fetchFirmAdvisorClientsFromEngagements(
  engagements: Engagement[],
  currentUserId: string
): Promise<Client[]> {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    return [];
  }

  try {
    // Fetch engagements from API to get advisor IDs
    const response = await fetch(`${API_BASE_URL}/api/engagements`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.error('Failed to fetch engagements for firm advisor');
      return [];
    }

    const rawEngagements = await response.json();
    const engagementsArray = Array.isArray(rawEngagements) ? rawEngagements : [];

    // Filter engagements where the user is primary or secondary advisor
    const userEngagements = engagementsArray.filter((engagement: any) => {
      const isPrimaryAdvisor = String(engagement.primary_advisor_id) === String(currentUserId);
      const secondaryIds = engagement.secondary_advisor_ids || [];
      const isSecondaryAdvisor = Array.isArray(secondaryIds) 
        ? secondaryIds.some((id: any) => String(id) === String(currentUserId))
        : false;
      return isPrimaryAdvisor || isSecondaryAdvisor;
    });

    // Extract unique clients from these engagements
    const clientMap = new Map<string, {
      id: string;
      name: string;
      email: string;
      engagements: number;
    }>();

    userEngagements.forEach((engagement: any) => {
      const clientId = engagement.client_id || engagement.clientId;
      if (!clientMap.has(String(clientId))) {
        const clientName = engagement.client_name || engagement.clientName || 'Unknown Client';
        // Try to extract email from name, or create a reasonable default
        let email = clientName;
        if (!clientName.includes('@')) {
          // Create a placeholder email from the name
          email = `${clientName.toLowerCase().replace(/[^a-z0-9]/g, '.').replace(/\.+/g, '.').replace(/^\.|\.$/g, '')}@client.local`;
        }
        
        clientMap.set(String(clientId), {
          id: String(clientId),
          name: clientName,
          email: email,
          engagements: 0,
        });
      }
      const client = clientMap.get(String(clientId))!;
      client.engagements += 1;
    });

    return Array.from(clientMap.values()).map(client => ({
      id: client.id,
      name: client.name,
      email: client.email,
      industry: '', // Will be set in clientsWithEngagements
      status: 'Active' as const,
      engagements: client.engagements,
      is_active: true,
      email_verified: false,
      role: 'client',
    }));
  } catch (error) {
    console.error('Error fetching firm advisor clients from engagements:', error);
    return [];
  }
}

/**
 * Fetches clients for advisor role (non-firm) from advisor-client associations API
 */
export async function fetchAdvisorClientsFromAssociations(): Promise<Client[]> {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    return [];
  }

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/advisor-client?status_filter=active`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      },
    );

    if (!response.ok) {
      console.error('Failed to fetch advisor clients');
      return [];
    }

    const associations = await response.json();

    // Map advisor-client associations to the Client shape
    return associations.map((assoc: any) => ({
      id: assoc.client_id,
      name: assoc.client_name || assoc.client_email || 'Unknown Client',
      email: assoc.client_email || '',
      industry: '',
      status: 'Active' as const,
      engagements: 0, // Will be updated from engagements data
      is_active: true,
      email_verified: false,
      role: 'client',
    }));
  } catch (error) {
    console.error('Error fetching advisor clients:', error);
    return [];
  }
}


export function getClientFetchingStrategy(user: User | null) {
  const isAdvisor = user?.role === 'advisor';
  const isFirmAdvisor = user?.role === 'firm_advisor';
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  const isFirmAdmin = user?.role === 'firm_admin';

  return {
    isAdvisor,
    isFirmAdvisor,
    isAdmin,
    isFirmAdmin,
    shouldUseEngagements: false, // Firm advisors now use associations instead of engagements
    shouldUseAssociations: isAdvisor || isFirmAdvisor, // Both regular and firm advisors use adv_client associations
    shouldUseFirmClients: isFirmAdmin, // Firm admin uses firm clients
    shouldUseAdminClients: isAdmin, // Admin uses all clients
  };
}

