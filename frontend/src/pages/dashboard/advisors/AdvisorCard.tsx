import { User, Mail, MoreHorizontal } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { Advisor } from '@/store/slices/firmReducer';

interface AdvisorCardProps {
  advisor: Advisor;
  onSuspend: (advisorId: string) => void;
  onReactivate: (advisorId: string) => void;
  onDelete: (advisorId: string) => void;
  onViewDetails?: (advisorId: string) => void;
  onAssociateClients?: (advisorId: string) => void;
}

export default function AdvisorCard({
  advisor,
  onSuspend,
  onReactivate,
  onDelete,
  onViewDetails,
  onAssociateClients,
}: AdvisorCardProps) {
  return (
    <div
      className="card-trinity p-5 hover:shadow-trinity-md cursor-pointer group"
      onClick={() => onViewDetails?.(advisor.id)}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
            <User className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold text-foreground group-hover:text-accent transition-colors">
              {advisor.name || 'Unknown'}
            </h3>
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="p-1.5 rounded-lg hover:bg-muted transition-colors opacity-0 group-hover:opacity-100"
              onClick={(e) => e.stopPropagation()}
            >
              <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {onAssociateClients && (
              <DropdownMenuItem 
                className="cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  onAssociateClients(advisor.id);
                }}
              >
                Associate Clients
              </DropdownMenuItem>
            )}
            {advisor.is_active ? (
              <DropdownMenuItem 
                className="cursor-pointer text-warning"
                onClick={(e) => {
                  e.stopPropagation();
                  onSuspend(advisor.id);
                }}
              >
                Suspend Advisor
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem 
                className="cursor-pointer text-green-600 hover:text-green-700"
                onClick={(e) => {
                  e.stopPropagation();
                  onReactivate(advisor.id);
                }}
              >
                Reactivate Advisor
              </DropdownMenuItem>
            )}
            <DropdownMenuItem 
              className="cursor-pointer text-destructive"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(advisor.id);
              }}
            >
              Remove from Firm
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Mail className="w-4 h-4" />
          <span>{advisor.email}</span>
        </div>
      </div>

      <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
        <div className="flex items-center gap-2">
          <span className={cn(
            "status-badge",
            advisor.is_active ? "status-success" : "status-warning"
          )}>
            {advisor.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
        <span className="text-xs text-muted-foreground capitalize">
          {advisor.role.replace('_', ' ')}
        </span>
      </div>
    </div>
  );
}

