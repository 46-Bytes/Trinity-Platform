import { ArrowUp, ArrowDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ValueMovement } from '@/store/slices/programGuideReducer';

interface ValueMovementViewProps {
  valueMovement: ValueMovement | null;
}

function ragColor(rag?: string | null): string {
  if (rag === 'Red') return 'text-destructive';
  if (rag === 'Amber') return 'text-warning';
  if (rag === 'Green') return 'text-success';
  return 'text-muted-foreground';
}

function DeltaIndicator({ delta }: { delta?: number | null }) {
  if (delta === null || delta === undefined) return <Minus className="h-3.5 w-3.5 text-muted-foreground" />;
  if (delta > 0) return <ArrowUp className="h-3.5 w-3.5 text-success" />;
  if (delta < 0) return <ArrowDown className="h-3.5 w-3.5 text-destructive" />;
  return <Minus className="h-3.5 w-3.5 text-muted-foreground" />;
}

export function ValueMovementView({ valueMovement }: ValueMovementViewProps) {
  if (!valueMovement || !valueMovement.has_comparison) {
    return (
      <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
        Retake the diagnostic to see how the business's value has moved since the last one. This comparison will
        appear once a second diagnostic has been completed.
      </div>
    );
  }

  const { overall_score_previous, overall_score_current, overall_score_delta, module_movements } = valueMovement;
  const isImprovement = (overall_score_delta ?? 0) > 0;

  return (
    <div className="space-y-4">
      <div
        className={cn(
          'flex items-center gap-4 rounded-md px-4 py-3',
          isImprovement ? 'bg-success/10' : 'bg-muted/50'
        )}
      >
        <div>
          <p className="text-xs text-muted-foreground">Previous</p>
          <p className="text-lg font-semibold">{overall_score_previous ?? '—'}</p>
        </div>
        <ArrowUp className="h-4 w-4 rotate-90 text-muted-foreground" />
        <div>
          <p className="text-xs text-muted-foreground">Current</p>
          <p className="text-lg font-semibold">{overall_score_current ?? '—'}</p>
        </div>
        <div
          className={cn(
            'flex items-center gap-1 ml-auto rounded-full px-2.5 py-1',
            isImprovement ? 'bg-success/10 text-success' : 'text-muted-foreground'
          )}
        >
          <DeltaIndicator delta={overall_score_delta} />
          <span className="text-sm font-medium">
            {overall_score_delta !== null && overall_score_delta !== undefined
              ? `${overall_score_delta > 0 ? '+' : ''}${overall_score_delta.toFixed(1)}`
              : '—'}
          </span>
        </div>
      </div>

      <div className="space-y-1.5">
        {module_movements.map((m) => (
          <div key={m.module_code} className="flex items-center justify-between text-sm py-1">
            <span className="text-muted-foreground">{m.module_name}</span>
            <div className="flex items-center gap-2">
              <span className={cn('text-xs', ragColor(m.previous_rag))}>{m.previous_score ?? '—'}</span>
              <DeltaIndicator delta={m.delta} />
              <span className={cn('text-xs font-medium', ragColor(m.current_rag))}>{m.current_score ?? '—'}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
