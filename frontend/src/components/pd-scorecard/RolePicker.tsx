import type { DraftStatus, PDScorecardRole } from '@/store/slices/pdScorecardReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, Circle, FileEdit } from 'lucide-react';
import { cn } from '@/lib/utils';

interface RolePickerProps {
  roles: PDScorecardRole[];
  activeRoleId: string | null;
  /** Which artefact's status to show against each role. */
  track: 'pd' | 'scorecard';
  onSelect: (roleId: string) => void;
}

const STATUS_LABELS: Record<DraftStatus, string> = {
  not_started: 'Not started',
  draft: 'Draft',
  approved: 'Approved',
};

const statusIcon = (status: DraftStatus) => {
  if (status === 'approved') return <CheckCircle2 className="h-4 w-4 text-green-600" />;
  if (status === 'draft') return <FileEdit className="h-4 w-4 text-amber-600" />;
  return <Circle className="h-4 w-4 text-muted-foreground" />;
};

export function RolePicker({ roles, activeRoleId, track, onSelect }: RolePickerProps) {
  const included = roles.filter((role) => role.included);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Roles</CardTitle>
        <CardDescription>
          Pick a role to work on. One at a time — finish it, then move to the next.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {included.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No roles are included in this build. Go back and confirm the role list.
          </p>
        )}

        {included.map((role) => {
          const status = track === 'pd' ? role.pd_status : role.scorecard_status;
          const isActive = role.id === activeRoleId;

          return (
            <button
              key={role.id}
              type="button"
              onClick={() => onSelect(role.id)}
              className={cn(
                'flex w-full items-center justify-between gap-3 rounded-md border p-3 text-left transition-colors',
                isActive ? 'border-primary bg-primary/5' : 'hover:bg-muted/40'
              )}
            >
              <div className="flex items-center gap-3 min-w-0">
                {statusIcon(status)}
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{role.role_title}</p>
                  {role.person_name && (
                    <p className="text-xs text-muted-foreground truncate">{role.person_name}</p>
                  )}
                </div>
              </div>
              <Badge
                variant={status === 'approved' ? 'default' : 'secondary'}
                className="flex-shrink-0"
              >
                {STATUS_LABELS[status]}
              </Badge>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}
