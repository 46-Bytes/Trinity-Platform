import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { User, UserRole, AuthState } from '@/types/auth';

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  switchRole: (role: UserRole) => void;
  refreshUser: () => Promise<void>;
  isImpersonating: boolean;
  originalUser: User | null;
  startImpersonation: (userId: string) => Promise<void>;
  stopImpersonation: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Backend API base URL - use env variable
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// Map backend user shape to frontend User type
function mapBackendUserToFrontend(backendUser: any): User {
  // Use role from backend, default to 'advisor' if not present
  const role = (backendUser.role || 'advisor') as UserRole;
  
  return {
    id: backendUser.id,
    email: backendUser.email,
    name: backendUser.name || backendUser.email,
    nickname: backendUser.nickname || undefined,
    role: role,
    avatar: backendUser.picture || undefined,
    bio: backendUser.bio || undefined,
    firmId: backendUser.firm_id || undefined,
    createdAt: backendUser.created_at || new Date().toISOString(),
    auth0Id: backendUser.auth0_id || undefined,
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,  // Start as true so ProtectedRoute waits for auth check
  });
  const [isImpersonating, setIsImpersonating] = useState(false);
  const [originalUser, setOriginalUser] = useState<User | null>(null);

  const login = useCallback(async (_email: string, _password: string) => {
    // Frontend does not handle credentials.
    // Always redirect to Auth0 Universal Login via backend.
    window.location.href = `${API_BASE_URL}/api/auth/login`;
  }, []);

  const logout = useCallback(() => {
    // Clear token from localStorage
    localStorage.removeItem('auth_token');
    
    // Redirect through backend to log out from Auth0
    window.location.href = `${API_BASE_URL}/api/auth/logout`;
  }, []);

  const switchRole = useCallback((role: UserRole) => {
    // For now we keep this as a no-op placeholder. Once we introduce real roles,
    // this can switch between roles based on backend data.
    setAuthState(prev => prev);
  }, []);

  const loadCurrentUser = useCallback(async () => {
    setAuthState(prev => ({ ...prev, isLoading: true }));
    
    // Get token from localStorage
    const token = localStorage.getItem('auth_token');
    
    console.log('🔍 loadCurrentUser called, token exists:', !!token);
    
    if (!token) {
      console.log('❌ No token in localStorage');
      setAuthState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
      setIsImpersonating(false);
      setOriginalUser(null);
      return;
    }
    
    try {
      // First check impersonation status
      const statusResponse = await fetch(`${API_BASE_URL}/api/auth/impersonation-status`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (statusResponse.ok) {
        const statusData = await statusResponse.json();
        if (statusData.is_impersonating) {
          setIsImpersonating(true);
          if (statusData.original_user) {
            setOriginalUser(mapBackendUserToFrontend(statusData.original_user));
          }
          if (statusData.impersonated_user) {
            const mappedUser = mapBackendUserToFrontend(statusData.impersonated_user);
            setAuthState({
              user: mappedUser,
              isAuthenticated: true,
              isLoading: false,
            });
            return;
          }
        } else {
          setIsImpersonating(false);
          setOriginalUser(null);
        }
      }

      console.log('📡 Fetching user from API...');
      const response = await fetch(`${API_BASE_URL}/api/auth/user`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      console.log('📥 Response status:', response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ API error:', response.status, errorText);
        // Token invalid, clear it
        localStorage.removeItem('auth_token');
        setAuthState({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
        setIsImpersonating(false);
        setOriginalUser(null);
        return;
      }

      const data = await response.json();
      console.log('✅ User data received:', data);

      if (data?.authenticated && data.user) {
        const mappedUser = mapBackendUserToFrontend(data.user);
        console.log('✅ User authenticated:', mappedUser.email);
        setAuthState({
          user: mappedUser,
          isAuthenticated: true,
          isLoading: false,
        });
      } else {
        console.log('❌ Invalid response format');
        localStorage.removeItem('auth_token');
        setAuthState({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
        setIsImpersonating(false);
        setOriginalUser(null);
      }
    } catch (error) {
      console.error('❌ Failed to load current user:', error);
      // Don't clear token on network errors - might be temporary
      setAuthState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
      setIsImpersonating(false);
      setOriginalUser(null);
    }
  }, []);

  const startImpersonation = useCallback(async (userId: string) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/users/${userId}/impersonate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to start impersonation' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to start impersonation`);
      }

      const data = await response.json();
      
      // Store new token
      localStorage.setItem('auth_token', data.access_token);
      
      // Update state
      if (data.user) {
        const mappedUser = mapBackendUserToFrontend(data.user);
        setAuthState({
          user: mappedUser,
          isAuthenticated: true,
          isLoading: false,
        });
      }
      
      if (data.original_user) {
        setOriginalUser(mapBackendUserToFrontend(data.original_user));
      }
      
      setIsImpersonating(true);
      
      // Redirect to dashboard for the impersonated user
      window.location.href = '/dashboard';
    } catch (error) {
      console.error('Failed to start impersonation:', error);
      throw error;
    }
  }, []);

  const stopImpersonation = useCallback(async () => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      // Store original user role before stopping (for redirect)
      const wasSuperAdmin = originalUser?.role === 'super_admin';

      const response = await fetch(`${API_BASE_URL}/api/auth/stop-impersonation`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to stop impersonation' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to stop impersonation`);
      }

      const data = await response.json();
      
      // Store new token
      localStorage.setItem('auth_token', data.access_token);
      
      // Update state
      if (data.user) {
        const mappedUser = mapBackendUserToFrontend(data.user);
        setAuthState({
          user: mappedUser,
          isAuthenticated: true,
          isLoading: false,
        });
      }
      
      setIsImpersonating(false);
      setOriginalUser(null);
      
      // Redirect based on original user role
      if (wasSuperAdmin) {
        // Redirect superadmin back to UsersPage
        window.location.href = '/dashboard/users';
      } else {
        // Redirect other roles to dashboard
        window.location.href = '/dashboard';
      }
    } catch (error) {
      console.error('Failed to stop impersonation:', error);
      throw error;
    }
  }, [originalUser]);

  // On initial load, ask the backend if there is an active Auth0 session.
  useEffect(() => {
    // Small delay to ensure component is fully mounted
    const timer = setTimeout(() => {
      loadCurrentUser();
    }, 100);
    
    return () => clearTimeout(timer);
  }, [loadCurrentUser]);

  return (
    <AuthContext.Provider value={{ 
      ...authState, 
      login, 
      logout, 
      switchRole, 
      refreshUser: loadCurrentUser,
      isImpersonating,
      originalUser,
      startImpersonation,
      stopImpersonation,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
