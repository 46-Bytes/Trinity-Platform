import type { DraftStatus, PDScorecardRole } from '@/store/slices/pdScorecardReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { CheckCircle2, FileEdit, Lock } from 'lucide-react';
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

export function RolePicker({ roles, activeRoleId, track, onSelect }: RolePickerProps) {
  const included = roles.filter((role) => role.included);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Roles</CardTitle>
        <CardDescription>
          {track === 'scorecard'
            ? 'A role opens once its position description is approved.'
            : 'Pick a role to work on. One at a time — finish it, then move to the next.'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {included.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No roles are included in this build. Go back and confirm the role list.
          </p>
        ) : (
          <RadioGroup value={activeRoleId ?? ''} onValueChange={onSelect} className="gap-2">
            {included.map((role) => {
              const status = track === 'pd' ? role.pd_status : role.scorecard_status;
              const isActive = role.id === activeRoleId;
              const isDone = status === 'approved';
              // The scorecard is generated from the approved PD, so a role stays
              // locked on this step until its position description is approved.
              const isLocked = track === 'scorecard' && role.pd_status !== 'approved';
              const inputId = `role-${track}-${role.id}`;

              return (
                <Label
                  key={role.id}
                  htmlFor={inputId}
                  className={cn(
                    'flex items-center justify-between gap-3 rounded-md border p-3 font-normal transition-colors',
                    isLocked
                      ? 'cursor-not-allowed border-dashed opacity-60'
                      : 'cursor-pointer hover:border-muted-foreground/30',
                    isDone && !isLocked && 'border-green-600/50 bg-green-500/5',
                    isActive && !isLocked && 'border-primary ring-1 ring-primary/40'
                  )}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <RadioGroupItem
                      value={role.id}
                      id={inputId}
                      disabled={isLocked}
                      className="flex-shrink-0"
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{role.role_title}</p>
                      {role.person_name && (
                        <p className="text-xs text-muted-foreground truncate">{role.person_name}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {isLocked ? (
                      <>
                        <Lock className="h-4 w-4 text-muted-foreground" />
                        <Badge variant="outline">PD not approved</Badge>
                      </>
                    ) : (
                      <>
                        {isDone && <CheckCircle2 className="h-4 w-4 text-green-600" />}
                        {status === 'draft' && <FileEdit className="h-4 w-4 text-amber-600" />}
                        <Badge
                          variant={isDone ? 'outline' : 'secondary'}
                          className={cn(
                            isDone &&
                              'border-green-600/40 bg-green-500/10 text-green-700 dark:text-green-400'
                          )}
                        >
                          {STATUS_LABELS[status]}
                        </Badge>
                      </>
                    )}
                  </div>
                </Label>
              );
            })}
          </RadioGroup>
        )}
      </CardContent>
    </Card>
  );
}
