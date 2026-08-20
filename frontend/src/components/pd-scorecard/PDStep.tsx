import { useEffect, useState } from 'react';
import { useAppDispatch } from '@/store/hooks';
import {
  approvePD,
  exportPD,
  generatePD,
  savePD,
  type PDContent,
  type PDResponsibilityTheme,
  type PDScorecard,
  type PDScorecardRole,
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
  ArrowRight,
  CheckCircle2,
  Download,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';

interface PDStepProps {
  build: PDScorecard | null;
  activeRoleId: string | null;
  isGenerating: boolean;
  isSaving: boolean;
  isExporting: boolean;
  onSelectRole: (roleId: string) => void;
  onBack: () => void;
  onComplete: () => void;
}

const emptyPD = (): PDContent => ({
  position_purpose: '',
  key_responsibilities: [],
  decision_making_authority: [],
  key_relationships: [],
  kpis: [],
  behavioural_expectations: [],
  transition_focus: [],
});

/** Bullets edit as one item per line — simple to reason about and quick to reorder. */
const toLines = (items?: string[] | null) => (items || []).join('\n');
const fromLines = (text: string) =>
  text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

interface BulletFieldProps {
  id: string;
  label: string;
  hint?: string;
  value: string[];
  rows?: number;
  onChange: (value: string[]) => void;
}

function BulletField({ id, label, hint, value, rows = 4, onChange }: BulletFieldProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      <Textarea
        id={id}
        value={toLines(value)}
        onChange={(e) => onChange(fromLines(e.target.value))}
        rows={rows}
        placeholder="One per line"
      />
    </div>
  );
}

export function PDStep({
  build,
  activeRoleId,
  isGenerating,
  isSaving,
  isExporting,
  onSelectRole,
  onBack,
  onComplete,
}: PDStepProps) {
  const dispatch = useAppDispatch();
  const [draft, setDraft] = useState<PDContent>(emptyPD());

  const roles = build?.roles || [];
  const role: PDScorecardRole | undefined = roles.find((r) => r.id === activeRoleId);

  // Load the stored draft whenever the selected role changes or is regenerated.
  // Keyed on id/updated_at rather than pd_content so typing is not overwritten.
  useEffect(() => {
    setDraft(role?.pd_content ? { ...emptyPD(), ...role.pd_content } : emptyPD());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role?.id, role?.updated_at]);

  const busy = isGenerating || isSaving || isExporting;
  const hasDraft = Boolean(role?.pd_content);

  const handleGenerate = async () => {
    if (!build || !role) return;
    try {
      await dispatch(generatePD({ buildId: build.id, roleId: role.id })).unwrap();
      toast.success('Draft position description ready for review');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Generation failed');
    }
  };

  const handleSave = async () => {
    if (!build || !role) return;
    try {
      await dispatch(savePD({ buildId: build.id, roleId: role.id, pdContent: draft })).unwrap();
      toast.success('Saved');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save');
    }
  };

  const handleApprove = async () => {
    if (!build || !role) return;
    try {
      // Save first so approval always covers what is on screen
      await dispatch(savePD({ buildId: build.id, roleId: role.id, pdContent: draft })).unwrap();
      await dispatch(approvePD({ buildId: build.id, roleId: role.id })).unwrap();
      // This toast lands on the "Create the scorecard" button, so keep it brief
      // and dismissible rather than blocking the next step.
      toast.success('Position description approved', { duration: 2000, closeButton: true });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to approve');
    }
  };

  const handleExport = async () => {
    if (!build || !role) return;
    try {
      await dispatch(
        exportPD({ buildId: build.id, roleId: role.id, roleTitle: role.role_title })
      ).unwrap();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Export failed');
    }
  };

  const updateTheme = (index: number, patch: Partial<PDResponsibilityTheme>) => {
    setDraft((prev) => ({
      ...prev,
      key_responsibilities: (prev.key_responsibilities || []).map((theme, i) =>
        i === index ? { ...theme, ...patch } : theme
      ),
    }));
  };

  return (
    <div className="space-y-6">
      <RolePicker roles={roles} activeRoleId={activeRoleId} track="pd" onSelect={onSelectRole} />

      {!role && (
        <Alert>
          <AlertDescription>Pick a role above to start its position description.</AlertDescription>
        </Alert>
      )}

      {role && (
        <>
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <CardTitle className="text-base">{role.role_title}</CardTitle>
                  <CardDescription>
                    Responsibilities come from the matrix rows flagged retain and gain. Rows flagged
                    lose become transition focus.
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

            {role.pd_status === 'approved' && (
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
                  <CardTitle className="text-base">1. Position Purpose</CardTitle>
                </CardHeader>
                <CardContent>
                  <Textarea
                    value={draft.position_purpose ?? ''}
                    onChange={(e) => setDraft((prev) => ({ ...prev, position_purpose: e.target.value }))}
                    rows={4}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">2. Key Responsibilities</CardTitle>
                  <CardDescription>Grouped into themes, one responsibility per line.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {(draft.key_responsibilities || []).map((theme, index) => (
                    <div key={index} className="space-y-3 rounded-md border p-3">
                      <div className="flex items-end gap-2">
                        <div className="flex-1 space-y-2">
                          <Label htmlFor={`theme-${index}`} className="text-xs">
                            Theme
                          </Label>
                          <Input
                            id={`theme-${index}`}
                            value={theme.theme}
                            onChange={(e) => updateTheme(index, { theme: e.target.value })}
                            placeholder="e.g. Operational Leadership"
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
                              key_responsibilities: (prev.key_responsibilities || []).filter(
                                (_, i) => i !== index
                              ),
                            }))
                          }
                          aria-label="Remove theme"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      <BulletField
                        id={`theme-items-${index}`}
                        label="Responsibilities"
                        value={theme.responsibilities || []}
                        onChange={(responsibilities) => updateTheme(index, { responsibilities })}
                      />
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
                        key_responsibilities: [
                          ...(prev.key_responsibilities || []),
                          { theme: '', responsibilities: [] },
                        ],
                      }))
                    }
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add a theme
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Sections 3 to 7</CardTitle>
                  <CardDescription>
                    One item per line. Leave transition focus empty and the section is left out of
                    the document.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <BulletField
                    id="decision-making"
                    label="3. Decision-Making Authority"
                    value={draft.decision_making_authority || []}
                    onChange={(value) =>
                      setDraft((prev) => ({ ...prev, decision_making_authority: value }))
                    }
                  />
                  <BulletField
                    id="relationships"
                    label="4. Key Relationships"
                    value={draft.key_relationships || []}
                    onChange={(value) => setDraft((prev) => ({ ...prev, key_relationships: value }))}
                  />
                  <BulletField
                    id="kpis"
                    label="5. Key Performance Indicators"
                    value={draft.kpis || []}
                    onChange={(value) => setDraft((prev) => ({ ...prev, kpis: value }))}
                  />
                  <BulletField
                    id="behaviours"
                    label="6. Behavioural Expectations"
                    value={draft.behavioural_expectations || []}
                    onChange={(value) =>
                      setDraft((prev) => ({ ...prev, behavioural_expectations: value }))
                    }
                  />
                  <BulletField
                    id="transition"
                    label="7. Transition Focus"
                    hint="Only for roles handing work over. Empty means the section is omitted."
                    value={draft.transition_focus || []}
                    onChange={(value) => setDraft((prev) => ({ ...prev, transition_focus: value }))}
                  />
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
                    {role.pd_status === 'approved' ? 'Re-approve' : 'Approve'}
                  </Button>
                  <Button variant="outline" onClick={handleExport} disabled={busy}>
                    {isExporting ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Download className="h-4 w-4 mr-2" />
                    )}
                    Download Word
                  </Button>
                </CardContent>
              </Card>
            </>
          )}
        </>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:justify-between">
        <Button variant="outline" onClick={onBack} disabled={busy}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button onClick={onComplete} disabled={busy || role?.pd_status !== 'approved'}>
          Create the scorecard
          <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}
