import { useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { DDHeaderRow, DDItemRow } from './DDItemRow';
import type { DDChecklist, DDItem, DDItemUpdate } from './types';

const ALL = '__all__';

const STATUS_FILTERS: { key: string; label: string; match: (i: DDItem) => boolean }[] = [
  { key: 'all', label: 'All', match: () => true },
  { key: 'open', label: 'Open', match: (i) => i.status !== 'yes' && i.status !== 'not_applicable' },
  { key: 'blank', label: 'Not started', match: (i) => !i.status },
  { key: 'in_progress', label: 'In progress', match: (i) => i.status === 'in_progress' },
  { key: 'no', label: 'Gaps', match: (i) => i.status === 'no' },
  { key: 'refer', label: 'Referred to VB', match: (i) => i.status === 'no' && i.gap_handling === 'refer' },
  { key: 'flag', label: 'Flagged', match: (i) => i.flag_for_m8 },
];

interface DDChecklistViewProps {
  checklist: DDChecklist;
  readOnly?: boolean;
  onOpenStage?: (stageCode: string) => void;
  onChange: (item: DDItem, changes: DDItemUpdate) => void;
}

/** The master DD checklist: every item, filterable, editing the same records as each stage. */
export function DDChecklistView({ checklist, readOnly = false, onOpenStage, onChange }: DDChecklistViewProps) {
  const [category, setCategory] = useState(ALL);
  const [stage, setStage] = useState(ALL);
  const [statusKey, setStatusKey] = useState('all');
  const [query, setQuery] = useState('');

  const categories = useMemo(
    () => [...new Map(checklist.items.map((i) => [i.category_code, `${i.category_code}. ${i.category}`])).entries()],
    [checklist.items]
  );

  const rows = useMemo(() => {
    const match = STATUS_FILTERS.find((f) => f.key === statusKey)?.match ?? (() => true);
    const q = query.trim().toLowerCase();
    return checklist.items.filter(
      (i) =>
        (category === ALL || i.category_code === category) &&
        (stage === ALL || i.stage_code === stage) &&
        match(i) &&
        (!q || `${i.document_required} ${i.action_step} ${i.sub_item}`.toLowerCase().includes(q))
    );
  }, [checklist.items, category, stage, statusKey, query]);

  const groups = useMemo(() => {
    const map = new Map<string, DDItem[]>();
    rows.forEach((i) => {
      const key = `${i.category_code}. ${i.category}`;
      map.set(key, [...(map.get(key) ?? []), i]);
    });
    return [...map.entries()];
  }, [rows]);

  const { stats } = checklist;
  const cards = [
    { value: stats.yes, label: 'Complete' },
    { value: stats.in_progress, label: 'In progress' },
    { value: stats.no, label: `No: gaps (${stats.referred} referred to Value Builder)` },
    { value: stats.not_applicable, label: 'Not applicable' },
    { value: stats.flagged, label: 'Flagged for review at M8' },
  ];

  return (
    <div className="card-trinity p-4 sm:p-7">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-heading text-xl font-bold tracking-tight">Due diligence checklist</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Master view of all {stats.total} items across {categories.length} categories. Each item also lives in its
            module{readOnly ? '.' : '. Edit in either place.'}
          </p>
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0} className="w-fit flex-shrink-0">
              <Button variant="outline" disabled className="font-semibold">
                Export to data room index
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>Available once Google Drive is connected</TooltipContent>
        </Tooltip>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:gap-5 md:grid-cols-5">
        {cards.map((c) => (
          <div key={c.label} className="rounded-xl border border-border px-4 py-4 sm:px-5">
            <p className="font-heading text-2xl font-bold tracking-tight">{c.value}</p>
            <p className="mt-1 text-sm leading-snug text-muted-foreground">{c.label}</p>
          </div>
        ))}
      </div>

      <div className="mb-3 flex flex-col gap-2.5 lg:flex-row lg:items-center">
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="h-11 w-full text-sm lg:w-[28rem]" aria-label="Category">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All categories</SelectItem>
            {categories.map(([code, label]) => (
              <SelectItem key={code} value={code}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={stage} onValueChange={setStage}>
          <SelectTrigger className="h-11 w-full text-sm lg:w-96" aria-label="Module or phase">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All modules</SelectItem>
            {checklist.stages.map((s) => (
              <SelectItem key={s.stage_code} value={s.stage_code}>
                {s.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search"
          className="h-11 w-full lg:w-60"
        />
      </div>
      <div className="mb-6 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setStatusKey(f.key)}
            className={cn(
              'rounded-full px-4 py-2 text-sm font-semibold transition-colors',
              statusKey === f.key
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:text-foreground'
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <DDHeaderRow />

      {groups.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          No items match these filters.
        </div>
      ) : (
        groups.map(([label, items]) => (
          <section key={label} className="mb-2">
            <h3 className="pb-1 pt-4 text-base font-bold">
              {label} <span className="ml-1.5 text-sm font-normal text-muted-foreground">{items.length} items</span>
            </h3>
            {items.map((item) => (
              <DDItemRow
                key={item.id}
                item={item}
                people={checklist.people}
                readOnly={readOnly}
                showStage
                onOpenStage={onOpenStage}
                onChange={(changes) => onChange(item, changes)}
              />
            ))}
          </section>
        ))
      )}
    </div>
  );
}
