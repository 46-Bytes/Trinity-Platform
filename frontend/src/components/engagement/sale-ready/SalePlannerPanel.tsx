import { useEffect, useState, type ReactNode } from 'react';

import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import type { SalePlanner, SalePlannerUpdate } from './types';

interface SalePlannerPanelProps {
  planner: SalePlanner;
  disabled?: boolean;
  onChange: (changes: SalePlannerUpdate) => void;
}

/** A text field that saves on blur, so each keystroke is not a request. */
function BlurText({
  value,
  onCommit,
  multiline = true,
  placeholder,
  disabled,
  id,
}: {
  value: string;
  onCommit: (value: string) => void;
  multiline?: boolean;
  placeholder?: string;
  disabled?: boolean;
  id?: string;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  const commit = () => draft !== value && onCommit(draft);
  return multiline ? (
    <Textarea
      id={id}
      value={draft}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      className="min-h-[52px] text-sm"
    />
  ) : (
    <Input
      id={id}
      value={draft}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      className="h-8 text-xs"
    />
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <div className="border-t border-border pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-bold">{title}</h3>
      {hint && <p className="mb-2 mt-0.5 text-xs text-muted-foreground">{hint}</p>}
      <div className={cn(!hint && 'mt-2')}>{children}</div>
    </div>
  );
}

/** The Sale Planner stage: sale decisions and the issues to address before listing. */
export function SalePlannerPanel({ planner, disabled = false, onChange }: SalePlannerPanelProps) {
  const { config } = planner;
  const valueStructures = config.value_proposition_structures.filter((o) => planner.sale_structures.includes(o.key));

  const toggleStructure = (key: string, on: boolean) => {
    const next = on
      ? config.sale_structures.map((o) => o.key).filter((k) => k === key || planner.sale_structures.includes(k))
      : planner.sale_structures.filter((k) => k !== key);
    onChange({ sale_structures: next });
  };

  return (
    <div className="space-y-5">
      <section className="card-trinity space-y-5 p-4 sm:p-6">
        <div>
          <h2 className="font-heading text-base font-semibold">Sale decisions</h2>
          {planner.updated_by_name && (
            <p className="mt-1 text-xs text-muted-foreground">Last changed by {planner.updated_by_name}</p>
          )}
        </div>

        <Section title="Type of sale">
          <RadioGroup
            value={planner.sale_type ?? ''}
            onValueChange={(v) => onChange({ sale_type: v })}
            disabled={disabled}
            className="gap-2"
          >
            {config.sale_types.map((o) => (
              <div key={o.key} className="flex items-center gap-2.5">
                <RadioGroupItem id={`sale-type-${o.key}`} value={o.key} />
                <Label htmlFor={`sale-type-${o.key}`} className="text-sm font-normal">
                  {o.label}
                </Label>
              </div>
            ))}
          </RadioGroup>
        </Section>

        <Section
          title="Structure of sale"
          hint="Tick every structure being considered. Note the value case for each under Best value proposition."
        >
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {config.sale_structures.map((o) => (
              <div key={o.key} className="flex items-center gap-2.5">
                <Checkbox
                  id={`structure-${o.key}`}
                  checked={planner.sale_structures.includes(o.key)}
                  disabled={disabled}
                  onCheckedChange={(v) => toggleStructure(o.key, v === true)}
                />
                <Label htmlFor={`structure-${o.key}`} className="text-sm font-normal">
                  {o.label}
                </Label>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Best value proposition">
          {valueStructures.length === 0 ? (
            <p className="text-xs text-muted-foreground">Select a structure above to record its value analysis.</p>
          ) : (
            <div className="space-y-3">
              {valueStructures.map((o) => (
                <div key={o.key}>
                  <Label htmlFor={`bvp-${o.key}`} className="mb-1.5 block text-sm">
                    {o.label}
                  </Label>
                  <BlurText
                    id={`bvp-${o.key}`}
                    value={planner.value_propositions[o.key] ?? ''}
                    disabled={disabled}
                    placeholder="Value analysis for this structure"
                    onCommit={(v) => onChange({ value_propositions: { [o.key]: v.trim() ? v : null } })}
                  />
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section title="Marketing plan">
          <div className="space-y-3">
            {config.marketing_questions.map((q) => (
              <div key={q.key}>
                <Label htmlFor={`mq-${q.key}`} className="mb-1.5 block text-sm">
                  {q.label}
                </Label>
                <BlurText
                  id={`mq-${q.key}`}
                  value={planner.marketing_answers[q.key] ?? ''}
                  disabled={disabled}
                  onCommit={(v) => onChange({ marketing_answers: { [q.key]: v.trim() ? v : null } })}
                />
              </div>
            ))}
          </div>
        </Section>
      </section>

      <section className="card-trinity p-4 sm:p-6">
        <h2 className="font-heading text-base font-semibold">Issues to be addressed</h2>
        <p className="mb-3 mt-1 text-xs text-muted-foreground">
          {planner.issues_addressed} of {planner.issues_total} addressed. Note where each one is handled.
        </p>
        {config.issues.map((issue) => {
          const state = planner.issues[issue.key] ?? { addressed: false, note: '' };
          return (
            <div
              key={issue.key}
              className="grid grid-cols-[1.5rem_1fr] items-start gap-x-3 gap-y-1.5 border-b border-border/60 py-2 last:border-b-0 sm:grid-cols-[1.5rem_1fr_1.2fr]"
            >
              <Checkbox
                id={`issue-${issue.key}`}
                checked={state.addressed}
                disabled={disabled}
                onCheckedChange={(v) => onChange({ issues: { [issue.key]: { addressed: v === true } } })}
                className="mt-0.5"
              />
              <Label
                htmlFor={`issue-${issue.key}`}
                className={cn('text-sm font-normal leading-snug', state.addressed && 'text-muted-foreground line-through')}
              >
                {issue.label}
              </Label>
              <div className="col-start-2 sm:col-start-auto">
                <BlurText
                  multiline={false}
                  value={state.note}
                  disabled={disabled}
                  placeholder="Where handled / note"
                  onCommit={(note) => onChange({ issues: { [issue.key]: { note } } })}
                />
              </div>
            </div>
          );
        })}
      </section>
    </div>
  );
}
