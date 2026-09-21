import { useEffect, useState } from 'react';
import { Flag, Upload } from 'lucide-react';

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { DD_STATUS_OPTIONS, GAP_OPTIONS } from './saleReadyGuide';
import type { DDItem, DDItemUpdate, SaleReadyPerson } from './types';

// Radix Select cannot hold an empty value, so "cleared" travels as this sentinel.
const NONE = '__none__';

/** One column template for the header and every row, so they line up. */
const DD_GRID = 'md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_9.5rem_8.5rem_2.5rem_2.5rem]';

/** The column headings above a list of DD rows, as in the mockup. Hidden on phones. */
export function DDHeaderRow() {
  return (
    <div
      className={cn(
        'hidden gap-3 border-b border-border pb-2 text-[11px] font-bold uppercase tracking-wider text-muted-foreground/70 md:grid',
        DD_GRID
      )}
    >
      <span>Document / information</span>
      <span>Action step</span>
      <span>Status</span>
      <span>Who</span>
      <span>File</span>
      <span>M8</span>
    </div>
  );
}

const STATUS_CLASS: Record<string, string> = {
  yes: 'border-success/30 bg-success/10 text-success font-semibold',
  in_progress: 'border-info/30 bg-info/10 text-info font-semibold',
  no: 'border-destructive/30 bg-destructive/10 text-destructive font-semibold',
  not_applicable: 'bg-muted text-muted-foreground',
};

interface DDItemRowProps {
  item: DDItem;
  people: SaleReadyPerson[];
  readOnly?: boolean;
  /** Master list: show the sub-item and owning stage under the document name. */
  showStage?: boolean;
  onOpenStage?: (stageCode: string) => void;
  onChange: (changes: DDItemUpdate) => void;
}

/** One DD item: the same record in the master checklist and in its stage. */
export function DDItemRow({ item, people, readOnly = false, showStage = false, onOpenStage, onChange }: DDItemRowProps) {
  const [notes, setNotes] = useState(item.notes ?? '');
  useEffect(() => setNotes(item.notes ?? ''), [item.notes]);

  const showNotes = (item.status && item.status !== 'yes') || !!item.notes;
  const responsible = people.find((p) => p.id === item.responsible_user_id);

  return (
    <div className="border-b border-border/60 py-3.5 last:border-b-0">
      <div className={cn('grid grid-cols-2 items-start gap-2 md:gap-3', DD_GRID)}>
        <div className="col-span-2 min-w-0 md:col-span-1">
          <p className={cn('text-[15px] leading-snug', item.status === 'yes' && 'text-muted-foreground')}>
            {item.document_required}
          </p>
          {showStage && (
            <p className="mt-1 text-xs font-semibold text-foreground/80">
              {item.sub_item_code} {item.sub_item} ·{' '}
              {onOpenStage ? (
                <button
                  type="button"
                  className="text-blue-700 hover:underline dark:text-blue-400"
                  onClick={() => onOpenStage(item.stage_code)}
                >
                  {item.stage_title}
                </button>
              ) : (
                item.stage_title
              )}
            </p>
          )}
        </div>
        <p className="col-span-2 text-sm leading-snug text-muted-foreground md:col-span-1">{item.action_step}</p>

        {readOnly ? (
          <>
            <span className={cn('w-fit rounded-md border px-2 py-1 text-xs', item.status ? STATUS_CLASS[item.status] : 'text-muted-foreground')}>
              {DD_STATUS_OPTIONS.find((o) => o.value === item.status)?.label ?? 'No status'}
            </span>
            <span className="text-xs text-muted-foreground">{responsible?.name ?? '—'}</span>
          </>
        ) : (
          <>
            <Select
              value={item.status ?? NONE}
              onValueChange={(v) => onChange({ status: v === NONE ? null : (v as DDItem['status']) })}
            >
              <SelectTrigger aria-label="Status" className={cn('h-9 rounded-lg text-sm', item.status && STATUS_CLASS[item.status])}>
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>No status</SelectItem>
                {DD_STATUS_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={item.responsible_user_id ?? NONE}
              onValueChange={(v) => onChange({ responsible_user_id: v === NONE ? null : v })}
            >
              <SelectTrigger aria-label="Responsible" className="h-9 rounded-lg text-sm">
                <SelectValue placeholder="Who" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Nobody</SelectItem>
                {people.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        )}

        <div className="col-span-2 flex items-center gap-2 md:contents">
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0} className="grid h-9 w-9 cursor-not-allowed place-items-center rounded-lg border-[1.5px] border-border text-muted-foreground/40">
                <Upload className="h-3.5 w-3.5" aria-hidden />
              </span>
            </TooltipTrigger>
            <TooltipContent>Uploads to the data room once Google Drive is connected</TooltipContent>
          </Tooltip>
          <button
            type="button"
            disabled={readOnly}
            onClick={() => onChange({ flag_for_m8: !item.flag_for_m8 })}
            aria-pressed={item.flag_for_m8}
            title="Needs review at Due Diligence Preparation"
            className={cn(
              'grid h-9 w-9 place-items-center rounded-lg border-[1.5px] border-border text-muted-foreground/40 disabled:cursor-default',
              item.flag_for_m8 && 'border-warning/40 bg-warning/10 text-warning'
            )}
          >
            <Flag className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      </div>

      {item.status === 'no' && (
        <div className="mt-2">
          {readOnly ? (
            <span className="text-xs font-semibold text-warning">
              {GAP_OPTIONS.find((o) => o.value === item.gap_handling)?.label ?? 'Gap handling not decided'}
            </span>
          ) : (
            <Select
              value={item.gap_handling ?? NONE}
              onValueChange={(v) => onChange({ gap_handling: v === NONE ? null : (v as DDItem['gap_handling']) })}
            >
              <SelectTrigger aria-label="Gap handling" className="h-8 w-full text-xs sm:w-72 border-warning/40 bg-warning/10 text-warning font-semibold">
                <SelectValue placeholder="How is this gap handled?" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>How is this gap handled?</SelectItem>
                {GAP_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      )}

      {showNotes &&
        (readOnly ? (
          item.notes && <p className="mt-2 text-xs text-muted-foreground">{item.notes}</p>
        ) : (
          <Textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            onBlur={() => notes !== (item.notes ?? '') && onChange({ notes })}
            placeholder="Notes are highly advised for any status other than Yes"
            className="mt-2 min-h-[44px] text-xs"
          />
        ))}
    </div>
  );
}
