import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { cn } from '@/lib/utils';
import { useGlobalDiagnosticPolling } from '@/hooks/useGlobalDiagnosticPolling';

export function DashboardLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Global diagnostic polling - tracks processing diagnostics across all pages
  useGlobalDiagnosticPolling();

  if (!isAuthenticated || !user) {
    return null;
  }

  return (
    <div className="min-h-screen flex w-full bg-background">
      <Sidebar 
        collapsed={sidebarCollapsed} 
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} 
      />
      
      <div className={cn(
        "flex-1 flex flex-col transition-all duration-300 overflow-x-hidden",
        sidebarCollapsed ? "ml-[72px]" : "ml-[260px]"
      )} style={{ width: '100%', maxWidth: '100vw', boxSizing: 'border-box' }}>
        <TopBar onMenuClick={() => setSidebarCollapsed(!sidebarCollapsed)} />
        
        <main className="flex-1 p-0 sm:p-1 md:p-2 lg:p-4 xl:p-6 overflow-auto overflow-x-hidden" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
          <div className="w-full mx-auto animate-fade-in" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
