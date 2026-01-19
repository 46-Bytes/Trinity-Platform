import { useAuth } from '@/context/AuthContext';
import { roleLabels, roleColors } from '@/types/auth';
import { Bell, Menu, LogOut, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function withCacheBuster(url: string, version?: string) {
  const v = version || String(Date.now());
  return `${url}${url.includes('?') ? '&' : '?'}v=${encodeURIComponent(v)}`;
}

interface TopBarProps {
  onMenuClick: () => void;
}

export function TopBar({ onMenuClick }: TopBarProps) {
  const { user, logout } = useAuth();

  return (
    <header className="h-16 bg-card border-b border-border flex items-center justify-between px-6 sticky top-0 z-40">
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="p-2 rounded-lg hover:bg-muted transition-colors lg:hidden"
        >
          <Menu className="w-5 h-5 text-muted-foreground" />
        </button>

      </div>

      <div className="flex items-center gap-3">
        {/* Current Role Display */}
        {user && (
          <span className={cn(
            "status-badge",
            roleColors[user.role]
          )}>
            {roleLabels[user.role]}
          </span>
        )}

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-muted transition-colors">
          <Bell className="w-5 h-5 text-muted-foreground" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-accent rounded-full" />
        </button>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-muted transition-colors">
              <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-medium text-sm overflow-hidden relative">
                {user?.avatar ? (
                  <img
                    src={withCacheBuster(
                      user.avatar.startsWith('http') ? user.avatar : `${API_BASE_URL}${user.avatar}`,
                      user.updatedAt || user.createdAt
                    )}
                    alt={user.nickname || user.name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      // Fallback to initial if image fails to load
                      const target = e.target as HTMLImageElement;
                      target.style.display = 'none';
                      const parent = target.parentElement;
                      if (parent) {
                        parent.textContent = (user?.nickname || user?.name || 'U').charAt(0);
                      }
                    }}
                  />
                ) : (
                  (user?.nickname || user?.name || 'U').charAt(0)
                )}
              </div>
              <ChevronDown className="w-4 h-4 text-muted-foreground hidden sm:block" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex flex-col">
                <span>{user?.nickname || user?.name || 'User'}</span>
                <span className="text-xs font-normal text-muted-foreground">{user?.email}</span>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout} className="text-destructive cursor-pointer">
              <LogOut className="w-4 h-4 mr-2" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
