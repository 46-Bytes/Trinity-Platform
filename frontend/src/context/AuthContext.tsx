import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { User, UserRole, AuthState } from '@/types/auth';

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  switchRole: (role: UserRole) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Backend API base URL - empty string uses the same origin (Vite proxy handles /api routes)
const API_BASE_URL = '';

// Map backend user shape to frontend User type
function mapBackendUserToFrontend(backendUser: any): User {
  // Use role from backend, default to 'advisor' if not present
  const role = (backendUser.role || 'advisor') as UserRole;
  
  return {
    id: backendUser.id,
    email: backendUser.email,
    name: backendUser.name || backendUser.email,
    role: role,
    avatar: backendUser.picture || undefined,
    createdAt: backendUser.created_at || new Date().toISOString(),
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,  // Start as true so ProtectedRoute waits for auth check
  });

  const login = useCallback(async (email: string, password: string) => {
    // We ignore email/password because Auth0 handles credentials.
    // Redirect to backend Auth0 login endpoint which then redirects to Universal Login.
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
      return;
    }
    
    try {
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
      }
    } catch (error) {
      console.error('❌ Failed to load current user:', error);
      // Don't clear token on network errors - might be temporary
    setAuthState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
    }
  }, []);

  // On initial load, ask the backend if there is an active Auth0 session.
  useEffect(() => {
    // Small delay to ensure component is fully mounted
    const timer = setTimeout(() => {
      loadCurrentUser();
    }, 100);
    
    return () => clearTimeout(timer);
  }, [loadCurrentUser]);

  return (
    <AuthContext.Provider value={{ ...authState, login, logout, switchRole }}>
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
