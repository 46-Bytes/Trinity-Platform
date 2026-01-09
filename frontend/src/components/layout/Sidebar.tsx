import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { NavLink } from '@/components/NavLink';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/utils';
import { 
  LayoutDashboard, 
  Users, 
  FolderOpen, 
  CheckSquare, 
  FileText, 
  Brain,
  Settings,
  Building2,
  UserCircle,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  BarChart3,
  Shield,
  MessageSquare,
  CreditCard
} from 'lucide-react';
import { UserRole } from '@/types/auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  roles: UserRole[];
}

const navItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, roles: ['super_admin', 'admin', 'advisor', 'client', 'firm_admin', 'firm_advisor'] },
  { label: 'Users', href: '/dashboard/users', icon: Users, roles: ['super_admin', 'admin'] },
  { label: 'Firms', href: '/dashboard/firms', icon: Building2, roles: ['super_admin'] },
  { label: 'Subscriptions', href: '/dashboard/subscriptions', icon: CreditCard, roles: ['super_admin'] },
  { label: 'Clients', href: '/dashboard/clients', icon: UserCircle, roles: ['admin', 'advisor', 'firm_admin', 'firm_advisor'] },
  { label: 'Advisors', href: '/dashboard/advisors', icon: Users, roles: ['firm_admin'] },
  { label: 'Engagements', href: '/dashboard/engagements', icon: FolderOpen, roles: ['super_admin', 'advisor', 'client', 'firm_admin', 'firm_advisor'] },
  { label: 'Tasks', href: '/dashboard/tasks', icon: CheckSquare, roles: ['super_admin', 'admin', 'advisor', 'client', 'firm_admin', 'firm_advisor'] },
  // { label: 'Documents', href: '/dashboard/documents', icon: FileText, roles: ['super_admin', 'advisor', 'client', 'firm_admin', 'firm_advisor'] },
  // { label: 'AI Tools', href: '/dashboard/ai-tools', icon: Brain, roles: ['super_admin', 'admin', 'advisor', 'firm_admin', 'firm_advisor'] },
  { label: 'Trinity Chat', href: '/dashboard/chat', icon: MessageSquare, roles: ['client'] },
  { label: 'Analytics', href: '/dashboard/analytics', icon: BarChart3, roles: ['super_admin', 'firm_admin'] },
  { label: 'Firm Management', href: '/dashboard/firm', icon: Building2, roles: ['firm_admin'] },
  { label: 'Security', href: '/dashboard/security', icon: Shield, roles: ['super_admin'] },
  { label: 'Settings', href: '/dashboard/settings', icon: Settings, roles: ['super_admin', 'admin', 'advisor', 'client', 'firm_admin', 'firm_advisor'] },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { user } = useAuth();
  const location = useLocation();
  const [firmsExpanded, setFirmsExpanded] = useState(false);

  const filteredItems = navItems.filter(item => 
    user && item.roles.includes(user.role) && item.href !== '/dashboard/firm' // Remove firm admin dashboard from superadmin
  );

  // Check if we're on a firm details page
  const firmDetailsMatch = location.pathname.match(/^\/dashboard\/firms\/([^/]+)/);
  const firmId = firmDetailsMatch ? firmDetailsMatch[1] : null;
  const isOnFirmDetails = firmId !== null;
  const isOnFirmsList = location.pathname === '/dashboard/firms';

  // Auto-expand firms section when on firm details or firms list
  useEffect(() => {
    if (user?.role === 'super_admin' && (isOnFirmDetails || isOnFirmsList)) {
      setFirmsExpanded(true);
    }
  }, [isOnFirmDetails, isOnFirmsList, user?.role]);

  // Nested navigation items for firm details
  const firmDetailsNavItems: NavItem[] = firmId ? [
    { label: 'Overview', href: `/dashboard/firms/${firmId}`, icon: LayoutDashboard, roles: ['super_admin'] },
    { label: 'Clients', href: `/dashboard/firms/${firmId}/clients`, icon: UserCircle, roles: ['super_admin'] },
    { label: 'Advisors', href: `/dashboard/firms/${firmId}/advisors`, icon: Users, roles: ['super_admin'] },
    { label: 'Engagements', href: `/dashboard/firms/${firmId}/engagements`, icon: FolderOpen, roles: ['super_admin'] },
    { label: 'Tasks', href: `/dashboard/firms/${firmId}/tasks`, icon: CheckSquare, roles: ['super_admin'] },
    { label: 'Analytics', href: `/dashboard/firms/${firmId}/analytics`, icon: BarChart3, roles: ['super_admin'] },
    { label: 'Subscription', href: `/dashboard/firms/${firmId}/subscription`, icon: CreditCard, roles: ['super_admin'] },
  ] : [];

  return (
    <aside className={cn(
      "fixed left-0 top-0 h-screen max-h-screen bg-sidebar flex flex-col transition-all duration-300 z-50",
      collapsed ? "w-[72px]" : "w-[260px]"
    )}>
      {/* Logo */}
      <div className="h-16 flex-shrink-0 flex items-center justify-between px-4 border-b border-sidebar-border">
        {!collapsed && (
          <div className="flex items-center gap-3">
            <img 
              src="/logo.png" 
              alt="Trinity Logo" 
              className="w-30 h-24 object-contain"
            />
          </div>
        )}
        {collapsed && (
          <img 
            src="/logo.png" 
            alt="Trinity Logo" 
            className="w-30 h-24 object-contain mx-auto"
          />
        )}
        <button
          onClick={onToggle}
          className={cn(
            "p-1.5 rounded-lg text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors",
            collapsed && "hidden"
          )}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 min-h-0 p-3 space-y-1 overflow-y-auto overflow-x-hidden">
        {filteredItems.map((item, index) => {
          // Special handling for Firms section for superadmin
          if (item.href === '/dashboard/firms' && user?.role === 'super_admin') {
            const isFirmsActive = isOnFirmsList || isOnFirmDetails;
            
            return (
              <div key={item.href} className="space-y-1">
                {/* Firms parent item - clickable to toggle or navigate */}
                <div className="flex items-center">
                  <NavLink
                    to={item.href}
                    className={cn(
                      "sidebar-item flex-1",
                      isFirmsActive && "sidebar-item-active",
                      collapsed && "justify-center px-0"
                    )}
                    style={{ animationDelay: `${index * 50}ms` }}
                  >
                    <item.icon className={cn("w-5 h-5 flex-shrink-0", isFirmsActive && "text-sidebar-primary")} />
                    {!collapsed && <span className="flex-1">{item.label}</span>}
                  </NavLink>
                  {!collapsed && isOnFirmDetails && (
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setFirmsExpanded(!firmsExpanded);
                      }}
                      className="p-1.5 ml-1 rounded hover:bg-sidebar-accent transition-colors flex-shrink-0"
                      aria-label={firmsExpanded ? "Collapse" : "Expand"}
                    >
                      {firmsExpanded ? (
                        <ChevronDown className="w-4 h-4 text-sidebar-foreground/60 transition-transform" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-sidebar-foreground/60 transition-transform" />
                      )}
                    </button>
                  )}
                </div>
                
                {/* Nested firm details items */}
                {!collapsed && isOnFirmDetails && firmsExpanded && firmDetailsNavItems.length > 0 && (
                  <div className="ml-4 mt-1 space-y-0.5 border-l-2 border-sidebar-border/40 pl-3 transition-all duration-200">
                    {firmDetailsNavItems.map((nestedItem, nestedIndex) => {
                      const isNestedActive = location.pathname === nestedItem.href || 
                        (nestedItem.href !== `/dashboard/firms/${firmId}` && location.pathname.startsWith(nestedItem.href));
                      
                      return (
                        <NavLink
                          key={nestedItem.href}
                          to={nestedItem.href}
                          className={cn(
                            "sidebar-item pl-4 text-sm py-2 min-h-[36px]",
                            isNestedActive && "sidebar-item-active bg-sidebar-accent/50"
                          )}
                          style={{ animationDelay: `${(index + nestedIndex + 1) * 30}ms` }}
                        >
                          <nestedItem.icon className={cn("w-4 h-4 flex-shrink-0", isNestedActive && "text-sidebar-primary")} />
                          <span>{nestedItem.label}</span>
                        </NavLink>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }
          
          // Regular navigation items
          const isActive = location.pathname === item.href || 
            (item.href !== '/dashboard' && location.pathname.startsWith(item.href) && 
             !location.pathname.startsWith('/dashboard/firms/'));
          
          return (
            <NavLink
              key={item.href}
              to={item.href}
              className={cn(
                "sidebar-item",
                isActive && "sidebar-item-active",
                collapsed && "justify-center px-0"
              )}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <item.icon className={cn("w-5 h-5 flex-shrink-0", isActive && "text-sidebar-primary")} />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Expand button when collapsed */}
      {collapsed && (
        <div className="flex-shrink-0 p-3 border-t border-sidebar-border">
          <button
            onClick={onToggle}
            className="w-full p-2 rounded-lg text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors flex items-center justify-center"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* User info */}
      {!collapsed && user && (
        <div className="flex-shrink-0 p-4 border-t border-sidebar-border">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-sidebar-accent flex items-center justify-center text-sidebar-foreground font-medium overflow-hidden relative">
              {user.avatar ? (
                <img
                  src={user.avatar.startsWith('http') ? user.avatar : `${API_BASE_URL}${user.avatar}`}
                  alt={user.nickname || user.name}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    // Fallback to initial if image fails to load
                    const target = e.target as HTMLImageElement;
                    target.style.display = 'none';
                    const parent = target.parentElement;
                    if (parent) {
                      parent.textContent = (user.nickname || user.name).charAt(0);
                    }
                  }}
                />
              ) : (
                (user.nickname || user.name).charAt(0)
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-sidebar-foreground truncate">
                {user.nickname || user.name}
              </p>
              <p className="text-xs text-sidebar-foreground/60 truncate">{user.email}</p>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
