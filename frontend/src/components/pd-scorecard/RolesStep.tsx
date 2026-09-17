import { useEffect, useState } from 'react';
import { useAppDispatch } from '@/store/hooks';
import {
  extractRoles,
  saveRoles,
  type PDScorecard,
  type RoleInput,
  type SuggestedRole,
} from '@/store/slices/pdScorecardReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ArrowLeft, ArrowRight, Loader2, Plus, Sparkles, Trash2, Users } from 'lucide-react';
import { toast } from 'sonner';

interface RolesStepProps {
  build: PDScorecard | null;
  suggestedRoles: SuggestedRole[];
  isExtracting: boolean;
  isSaving: boolean;
  onBack: () => void;
  onComplete: () => void;
}

/** A row in the editable role list. */
interface EditableRole {
  id?: string;
  role_title: string;
  person_name: string;
  included: boolean;
}

const blankRole = (): EditableRole => ({ role_title: '', person_name: '', included: true });

export function RolesStep({
  build,
  suggestedRoles,
  isExtracting,
  isSaving,
  onBack,
  onComplete,
}: RolesStepProps) {
  const dispatch = useAppDispatch();
  const [roles, setRoles] = useState<EditableRole[]>([]);

  const buildId = build?.id;
  const savedRoles = build?.roles;
  const hasMatrixRows = Boolean(build?.matrix_rows?.length);

  // Saved roles win over suggestions, so confirmed work is never overwritten
  useEffect(() => {
    if (savedRoles?.length) {
      setRoles(
        savedRoles.map((role) => ({
          id: role.id,
          role_title: role.role_title,
          person_name: role.person_name ?? '',
          included: role.included,
        }))
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildId, savedRoles?.length]);

  // Seed from suggestions only while the list is still empty
  useEffect(() => {
    if (suggestedRoles.length === 0) return;
    setRoles((prev) => {
      if (prev.length > 0) return prev;
      return suggestedRoles.map((role) => ({
        role_title: role.role_title ?? '',
        person_name: role.person_name ?? '',
        included: true,
      }));
    });
  }, [suggestedRoles]);

  const handleExtract = async () => {
    if (!build) return;
    try {
      await dispatch(extractRoles({ buildId: build.id })).unwrap();
      toast.success('Roles matrix read');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not read the matrix');
    }
  };

  const updateRole = (index: number, patch: Partial<EditableRole>) => {
    setRoles((prev) => prev.map((role, i) => (i === index ? { ...role, ...patch } : role)));
  };

  const handleContinue = async () => {
    if (!build) return;

    const cleaned: RoleInput[] = roles
      .filter((role) => role.role_title.trim())
      .map((role) => ({
        id: role.id,
        role_title: role.role_title.trim(),
        person_name: role.person_name.trim() || null,
        included: role.included,
      }));

    if (cleaned.length === 0) {
      toast.error('Add at least one role');
      return;
    }
    if (!cleaned.some((role) => role.included)) {
      toast.error('Include at least one role in the build');
      return;
    }

    try {
      await dispatch(saveRoles({ buildId: build.id, roles: cleaned })).unwrap();
      onComplete();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save the roles');
    }
  };

  const busy = isExtracting || isSaving;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Roles in the matrix</CardTitle>
          <CardDescription>
            Read the matrix to find the roles it covers, then confirm the titles and choose which to
            build. You work through one role at a time from here.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!hasMatrixRows && (
            <Alert>
              <AlertDescription>
                The matrix has not been read yet. Run it to pull out the rows and the roles.
              </AlertDescription>
            </Alert>
          )}

          <Button variant="outline" onClick={handleExtract} disabled={busy}>
            {isExtracting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Reading the matrix...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                {hasMatrixRows ? 'Read the matrix again' : 'Read the matrix'}
              </>
            )}
          </Button>

          {hasMatrixRows && (
            <p className="text-sm text-muted-foreground">
              {build?.matrix_rows?.length} row(s) found in the matrix.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Confirm the roles</CardTitle>
          <CardDescription>
            Edit any title that came through wrong. Untick a role to leave it out of this build.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {roles.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <Users className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                No roles yet. Read the matrix above, or add one by hand.
              </p>
            </div>
          )}

          {roles.map((role, index) => (
            <div
              key={role.id ?? `new-${index}`}
              className="flex flex-col gap-3 rounded-md border p-3 sm:flex-row sm:items-end"
            >
              <div className="flex items-center gap-3 sm:pb-2">
                <Checkbox
                  id={`include-${index}`}
                  checked={role.included}
                  onCheckedChange={(checked) => updateRole(index, { included: checked === true })}
                />
                <Label htmlFor={`include-${index}`} className="text-sm font-normal">
                  Include
                </Label>
              </div>

              <div className="flex-1 space-y-2">
                <Label htmlFor={`title-${index}`} className="text-xs">
                  Role title
                </Label>
                <Input
                  id={`title-${index}`}
                  value={role.role_title}
                  onChange={(e) => updateRole(index, { role_title: e.target.value })}
                  placeholder="e.g. General Manager"
                />
              </div>

              <div className="flex-1 space-y-2">
                <Label htmlFor={`person-${index}`} className="text-xs">
                  Person (optional)
                </Label>
                <Input
                  id={`person-${index}`}
                  value={role.person_name}
                  onChange={(e) => updateRole(index, { person_name: e.target.value })}
                  placeholder="e.g. Scott"
                />
              </div>

              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => setRoles((prev) => prev.filter((_, i) => i !== index))}
                aria-label="Remove role"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => setRoles((prev) => [...prev, blankRole()])}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add a role
          </Button>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 sm:flex-row sm:justify-between">
        <Button variant="outline" onClick={onBack} disabled={busy}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button onClick={handleContinue} disabled={busy || roles.length === 0}>
          {isSaving ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              Continue
              <ArrowRight className="h-4 w-4 ml-2" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
