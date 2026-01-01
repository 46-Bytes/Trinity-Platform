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
  BarChart3,
  Shield,
  MessageSquare
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
  { label: 'Clients', href: '/dashboard/clients', icon: UserCircle, roles: ['super_admin', 'admin', 'advisor', 'firm_admin', 'firm_advisor'] },
  { label: 'Engagements', href: '/dashboard/engagements', icon: FolderOpen, roles: ['super_admin', 'admin', 'advisor', 'client', 'firm_admin', 'firm_advisor'] },
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

  const filteredItems = navItems.filter(item => 
    user && item.roles.includes(user.role)
  );

  return (
    <aside className={cn(
      "fixed left-0 top-0 h-screen bg-sidebar flex flex-col transition-all duration-300 z-50",
      collapsed ? "w-[72px]" : "w-[260px]"
    )}>
      {/* Logo */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-sidebar-border">
        {!collapsed && (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-sidebar-primary flex items-center justify-center">
              <span className="text-sidebar-primary-foreground font-bold text-sm">T</span>
            </div>
            <span className="font-heading font-semibold text-sidebar-foreground">Trinity</span>
          </div>
        )}
        {collapsed && (
          <div className="w-8 h-8 rounded-lg bg-sidebar-primary flex items-center justify-center mx-auto">
            <span className="text-sidebar-primary-foreground font-bold text-sm">T</span>
          </div>
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
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {filteredItems.map((item, index) => {
          const isActive = location.pathname === item.href || 
            (item.href !== '/dashboard' && location.pathname.startsWith(item.href));
          
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
        <div className="p-3 border-t border-sidebar-border">
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
        <div className="p-4 border-t border-sidebar-border">
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
