import { useEffect, useState } from 'react';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import type { Closeout, CloseoutUpdate } from './types';

interface CloseoutPanelProps {
  closeout: Closeout;
  isSaving: boolean;
  onChange: (changes: CloseoutUpdate) => void;
  /** Saves any unsaved note with the close, in the same request. */
  onClose: (changes: CloseoutUpdate, confirmWithoutReferral: boolean) => void;
  onReopen: () => void;
}

function formatDate(value: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
}

/**
 * The final action of the program. Closing ends the engagement in Trinity
 * (lifecycle status "ended"); reopening recommences it.
 */
export function CloseoutPanel({ closeout, isSaving, onChange, onClose, onReopen }: CloseoutPanelProps) {
  const [ongoing, setOngoing] = useState(closeout.ongoing_assistance ?? '');
  const [confirmOpen, setConfirmOpen] = useState(false);
  useEffect(() => setOngoing(closeout.ongoing_assistance ?? ''), [closeout.ongoing_assistance]);

  const pendingNote = ongoing !== (closeout.ongoing_assistance ?? '') ? { ongoing_assistance: ongoing } : {};
  const requestClose = () => {
    if (closeout.referred_to_benchmark) onClose(pendingNote, false);
    else setConfirmOpen(true);
  };

  if (closeout.is_closed) {
    return (
      <section className="card-trinity border-success/30 bg-success/5 p-4 sm:p-6">
        <h2 className="font-heading text-base font-semibold">Close the program</h2>
        <div className="mt-3 rounded-lg border border-success/30 bg-success/10 px-3.5 py-3 text-sm text-success">
          Program closed on {formatDate(closeout.closed_at)}
          {closeout.closed_by_name ? ` by ${closeout.closed_by_name}` : ''}.{' '}
          {closeout.fresh_appraisal_required && 'Fresh appraisal to be run. '}
          {closeout.referred_to_benchmark
            ? 'Referred to Benchmark Business Sales for listing. '
            : 'Not referred to Benchmark Business Sales. '}
          {closeout.ongoing_assistance
            ? `Ongoing assistance: ${closeout.ongoing_assistance}`
            : 'No ongoing assistance recorded.'}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">The engagement has ended in Trinity.</p>
        <Button variant="outline" className="mt-4" disabled={isSaving} onClick={onReopen}>
          Reopen program
        </Button>
      </section>
    );
  }

  return (
    <section className={cn('card-trinity border-destructive/30 p-4 sm:p-6')}>
      <h2 className="font-heading text-base font-semibold">Close the program</h2>
      <p className="mb-4 mt-1 text-xs text-muted-foreground">
        The final action. Confirm the close-out decisions, then close. This ends the engagement in Trinity.
      </p>

      <div className="space-y-2.5">
        <div className="flex items-center gap-2.5">
          <Checkbox
            id="closeout-reappraise"
            checked={closeout.fresh_appraisal_required}
            disabled={isSaving}
            onCheckedChange={(v) => onChange({ fresh_appraisal_required: v === true })}
          />
          <Label htmlFor="closeout-reappraise" className="text-sm font-normal">
            A fresh appraisal is required before listing
          </Label>
        </div>
        <div className="flex items-center gap-2.5">
          <Checkbox
            id="closeout-refer"
            checked={closeout.referred_to_benchmark}
            disabled={isSaving}
            onCheckedChange={(v) => onChange({ referred_to_benchmark: v === true })}
          />
          <Label htmlFor="closeout-refer" className="text-sm font-normal">
            Refer the client to Benchmark Business Sales for listing
          </Label>
        </div>
      </div>

      <Label htmlFor="closeout-ongoing" className="mb-1.5 mt-4 block text-sm">
        Ongoing assistance
      </Label>
      <Textarea
        id="closeout-ongoing"
        value={ongoing}
        disabled={isSaving}
        placeholder="What ongoing assistance is agreed, if any"
        onChange={(e) => setOngoing(e.target.value)}
        onBlur={(e) => {
          // The close request carries the note itself; saving it separately would race the close.
          if ((e.relatedTarget as HTMLElement | null)?.dataset.closeProgram) return;
          if (pendingNote.ongoing_assistance !== undefined) onChange(pendingNote);
        }}
        className="min-h-[52px] text-sm"
      />

      <Button variant="destructive" className="mt-4" disabled={isSaving} onClick={requestClose} data-close-program="true">
        Close program
      </Button>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Close without a referral?</AlertDialogTitle>
            <AlertDialogDescription>
              The client is not being referred to Benchmark Business Sales for listing. Closing the program also ends
              the engagement in Trinity. It can be reopened later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => onClose(pendingNote, true)}>Close program</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
