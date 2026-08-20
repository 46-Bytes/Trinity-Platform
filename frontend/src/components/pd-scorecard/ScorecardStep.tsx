import { useEffect, useState } from 'react';
import { useAppDispatch } from '@/store/hooks';
import {
  approveScorecard,
  exportScorecard,
  generateScorecard,
  saveScorecard,
  type PDScorecard,
  type PDScorecardRole,
  type ScorecardBehaviourRow,
  type ScorecardContent,
  type ScorecardMilestoneRow,
  type ScorecardResponsibilityRow,
} from '@/store/slices/pdScorecardReducer';
import { RolePicker } from './RolePicker';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';

interface ScorecardStepProps {
  build: PDScorecard | null;
  activeRoleId: string | null;
  isGenerating: boolean;
  isSaving: boolean;
  isExporting: boolean;
  onSelectRole: (roleId: string) => void;
  onBack: () => void;
}

const emptyScorecard = (): ScorecardContent => ({
  role_purpose: '',
  responsibilities: [],
  behaviours: [],
  milestones: [],
});

export function ScorecardStep({
  build,
  activeRoleId,
  isGenerating,
  isSaving,
  isExporting,
  onSelectRole,
  onBack,
}: ScorecardStepProps) {
  const dispatch = useAppDispatch();
  const [draft, setDraft] = useState<ScorecardContent>(emptyScorecard());

  const roles = build?.roles || [];
  const role: PDScorecardRole | undefined = roles.find((r) => r.id === activeRoleId);

  // Keyed on id/updated_at rather than scorecard_content so typing is not overwritten.
  useEffect(() => {
    setDraft(
      role?.scorecard_content ? { ...emptyScorecard(), ...role.scorecard_content } : emptyScorecard()
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role?.id, role?.updated_at]);

  const busy = isGenerating || isSaving || isExporting;
  const hasDraft = Boolean(role?.scorecard_content);
  const pdApproved = role?.pd_status === 'approved';

  const handleGenerate = async () => {
    if (!build || !role) return;
    try {
      await dispatch(generateScorecard({ buildId: build.id, roleId: role.id })).unwrap();
      toast.success('Draft scorecard ready for review');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Generation failed');
    }
  };

  const handleSave = async () => {
    if (!build || !role) return;
    try {
      await dispatch(
        saveScorecard({ buildId: build.id, roleId: role.id, scorecardContent: draft })
      ).unwrap();
      toast.success('Saved');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save');
    }
  };

  const handleApprove = async () => {
    if (!build || !role) return;
    try {
      // Save first so approval always covers what is on screen
      await dispatch(
        saveScorecard({ buildId: build.id, roleId: role.id, scorecardContent: draft })
      ).unwrap();
      await dispatch(approveScorecard({ buildId: build.id, roleId: role.id })).unwrap();
      toast.success('Scorecard approved');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to approve');
    }
  };

  const handleExport = async () => {
    if (!build || !role) return;
    try {
      await dispatch(
        exportScorecard({ buildId: build.id, roleId: role.id, roleTitle: role.role_title })
      ).unwrap();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Export failed');
    }
  };

  const updateResponsibility = (index: number, patch: Partial<ScorecardResponsibilityRow>) => {
    setDraft((prev) => ({
      ...prev,
      responsibilities: (prev.responsibilities || []).map((row, i) =>
        i === index ? { ...row, ...patch } : row
      ),
    }));
  };

  const updateBehaviour = (index: number, patch: Partial<ScorecardBehaviourRow>) => {
    setDraft((prev) => ({
      ...prev,
      behaviours: (prev.behaviours || []).map((row, i) => (i === index ? { ...row, ...patch } : row)),
    }));
  };

  const updateMilestone = (index: number, patch: Partial<ScorecardMilestoneRow>) => {
    setDraft((prev) => ({
      ...prev,
      milestones: (prev.milestones || []).map((row, i) => (i === index ? { ...row, ...patch } : row)),
    }));
  };

  return (
    <div className="space-y-6">
      <RolePicker
        roles={roles}
        activeRoleId={activeRoleId}
        track="scorecard"
        onSelect={onSelectRole}
      />

      {!role && (
        <Alert>
          <AlertDescription>Pick a role above to build its scorecard.</AlertDescription>
        </Alert>
      )}

      {role && !pdApproved && (
        <Alert>
          <AlertDescription>
            Approve the position description for {role.role_title} before creating its scorecard.
          </AlertDescription>
        </Alert>
      )}

      {role && pdApproved && (
        <>
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <CardTitle className="text-base">{role.role_title}</CardTitle>
                  <CardDescription>
                    Rating and comment columns, the 1-5 dropdowns and the summary block are added on
                    export.
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  onClick={handleGenerate}
                  disabled={busy}
                  className="flex-shrink-0"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4 mr-2" />
                      {hasDraft ? 'Regenerate draft' : 'Generate draft'}
                    </>
                  )}
                </Button>
              </div>
            </CardHeader>

            {role.scorecard_status === 'approved' && (
              <CardContent>
                <Alert>
                  <CheckCircle2 className="h-4 w-4" />
                  <AlertDescription>
                    Approved. Editing below returns it to draft and needs re-approval.
                  </AlertDescription>
                </Alert>
              </CardContent>
            )}
          </Card>

          {hasDraft && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Role Purpose</CardTitle>
                </CardHeader>
                <CardContent>
                  <Textarea
                    value={draft.role_purpose ?? ''}
                    onChange={(e) => setDraft((prev) => ({ ...prev, role_purpose: e.target.value }))}
                    rows={3}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Responsibilities &amp; Outcomes</CardTitle>
                  <CardDescription>One row per focus area.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {(draft.responsibilities || []).map((row, index) => (
                    <div key={index} className="space-y-3 rounded-md border p-3">
                      <div className="flex items-end gap-2">
                        <div className="flex-1 space-y-2">
                          <Label htmlFor={`focus-${index}`} className="text-xs">
                            Focus area
                          </Label>
                          <Input
                            id={`focus-${index}`}
                            value={row.focus_area ?? ''}
                            onChange={(e) => updateResponsibility(index, { focus_area: e.target.value })}
                          />
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={busy}
                          onClick={() =>
                            setDraft((prev) => ({
                              ...prev,
                              responsibilities: (prev.responsibilities || []).filter(
                                (_, i) => i !== index
                              ),
                            }))
                          }
                          aria-label="Remove focus area"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor={`accountability-${index}`} className="text-xs">
                          Core accountability
                        </Label>
                        <Textarea
                          id={`accountability-${index}`}
                          value={row.core_accountability ?? ''}
                          onChange={(e) =>
                            updateResponsibility(index, { core_accountability: e.target.value })
                          }
                          rows={2}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor={`indicators-${index}`} className="text-xs">
                          Performance indicators / outcomes
                        </Label>
                        <Textarea
                          id={`indicators-${index}`}
                          value={row.performance_indicators ?? ''}
                          onChange={(e) =>
                            updateResponsibility(index, { performance_indicators: e.target.value })
                          }
                          rows={2}
                        />
                      </div>
                    </div>
                  ))}

                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() =>
                      setDraft((prev) => ({
                        ...prev,
                        responsibilities: [...(prev.responsibilities || []), {}],
                      }))
                    }
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add a focus area
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Behaviour &amp; Leadership Expectations</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {(draft.behaviours || []).map((row, index) => (
                    <div key={index} className="flex flex-col gap-3 rounded-md border p-3 sm:flex-row sm:items-end">
                      <div className="flex-1 space-y-2">
                        <Label htmlFor={`behaviour-${index}`} className="text-xs">
                          Behavioural focus
                        </Label>
                        <Input
                          id={`behaviour-${index}`}
                          value={row.behavioural_focus ?? ''}
                          onChange={(e) => updateBehaviour(index, { behavioural_focus: e.target.value })}
                        />
                      </div>
                      <div className="flex-[2] space-y-2">
                        <Label htmlFor={`demonstration-${index}`} className="text-xs">
                          Expected demonstration
                        </Label>
                        <Input
                          id={`demonstration-${index}`}
                          value={row.expected_demonstration ?? ''}
                          onChange={(e) =>
                            updateBehaviour(index, { expected_demonstration: e.target.value })
                          }
                        />
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={busy}
                        onClick={() =>
                          setDraft((prev) => ({
                            ...prev,
                            behaviours: (prev.behaviours || []).filter((_, i) => i !== index),
                          }))
                        }
                        aria-label="Remove behaviour"
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
                    onClick={() =>
                      setDraft((prev) => ({ ...prev, behaviours: [...(prev.behaviours || []), {}] }))
                    }
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add a behaviour
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Transition Milestones</CardTitle>
                  <CardDescription>
                    Optional. Leave empty and the section is left out of the workbook.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {(draft.milestones || []).map((row, index) => (
                    <div key={index} className="flex flex-col gap-3 rounded-md border p-3 sm:flex-row sm:items-end">
                      <div className="flex-[2] space-y-2">
                        <Label htmlFor={`milestone-${index}`} className="text-xs">
                          Milestone
                        </Label>
                        <Input
                          id={`milestone-${index}`}
                          value={row.milestone ?? ''}
                          onChange={(e) => updateMilestone(index, { milestone: e.target.value })}
                        />
                      </div>
                      <div className="flex-1 space-y-2">
                        <Label htmlFor={`target-${index}`} className="text-xs">
                          Target date
                        </Label>
                        <Input
                          id={`target-${index}`}
                          value={row.target_date ?? ''}
                          onChange={(e) => updateMilestone(index, { target_date: e.target.value })}
                          placeholder="e.g. FY26 H1"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={busy}
                        onClick={() =>
                          setDraft((prev) => ({
                            ...prev,
                            milestones: (prev.milestones || []).filter((_, i) => i !== index),
                          }))
                        }
                        aria-label="Remove milestone"
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
                    onClick={() =>
                      setDraft((prev) => ({ ...prev, milestones: [...(prev.milestones || []), {}] }))
                    }
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add a milestone
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex flex-col gap-3 pt-6 sm:flex-row sm:flex-wrap">
                  <Button variant="outline" onClick={handleSave} disabled={busy}>
                    {isSaving ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4 mr-2" />
                    )}
                    Save draft
                  </Button>
                  <Button onClick={handleApprove} disabled={busy}>
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    {role.scorecard_status === 'approved' ? 'Re-approve' : 'Approve'}
                  </Button>
                  <Button variant="outline" onClick={handleExport} disabled={busy}>
                    {isExporting ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Download className="h-4 w-4 mr-2" />
                    )}
                    Download Excel
                  </Button>
                </CardContent>
              </Card>
            </>
          )}
        </>
      )}

      <div className="flex justify-start">
        <Button variant="outline" onClick={onBack} disabled={busy}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to position description
        </Button>
      </div>
    </div>
  );
}
