import { useEffect, useMemo, useState } from 'react';

export interface EngagementMember {
  id: string;
  name?: string | null;
  role?: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Assignable people on a Sale Ready engagement (advisors + clients), for
 * lead-advisor and responsible-person pickers. Shared by G1/G3/G4.
 */
export function useEngagementMembers(engagementId: string) {
  const [members, setMembers] = useState<EngagementMember[]>([]);

  useEffect(() => {
    if (!engagementId) return;
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/sale-ready/engagements/${engagementId}/members`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      credentials: 'include',
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (!cancelled) setMembers(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        if (!cancelled) setMembers([]);
      });
    return () => {
      cancelled = true;
    };
  }, [engagementId]);

  const nameById = useMemo(() => {
    const map: Record<string, string> = {};
    members.forEach((m) => {
      map[m.id] = m.name || m.id;
    });
    return map;
  }, [members]);

  return { members, nameById };
}
