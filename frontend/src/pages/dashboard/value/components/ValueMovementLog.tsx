import { ChevronLeft, ChevronRight, UserCog, Sparkles } from 'lucide-react';
import { VALUE_BUILDER_MODULES } from '@/lib/valueDrivers';
import type { ValuePoint } from '@/lib/valueDashboardService';
import { formatAUD } from '@/lib/utils';
import { formatMonthLong } from '../chartTheme';
import { Delta } from './ValueDashboardChrome';

interface ValueMovementLogProps {
  history: ValuePoint[];
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
}

/**
 * The change or changes behind the selected point on the uplift chart.
 *
 * The previous/next buttons exist so the movement history is reachable without
 * clicking points on an SVG.
 */
export function ValueMovementLog({ history, selectedIndex, onSelectIndex }: ValueMovementLogProps) {
  const point = history[selectedIndex];
  if (!point) return null;

  const previousValue = selectedIndex > 0 ? history[selectedIndex - 1].value : point.value;
  const movement = point.value - previousValue;
  const changes = point.events.filter((event) => event.delta !== 0 || selectedIndex === 0);

  return (
    <section className="card-trinity p-6 flex flex-col">
      <div className="flex items-start justify-between gap-3 mb-1">
        <h3 className="font-heading font-semibold text-lg text-foreground">What Moved the Value</h3>
        <div className="flex items-center gap-1 flex-shrink-0">
          <StepButton
            label="Previous month"
            icon={ChevronLeft}
            disabled={selectedIndex === 0}
            onClick={() => onSelectIndex(selectedIndex - 1)}
          />
          <StepButton
            label="Next month"
            icon={ChevronRight}
            disabled={selectedIndex === history.length - 1}
            onClick={() => onSelectIndex(selectedIndex + 1)}
          />
        </div>
      </div>

      <p className="text-sm text-muted-foreground">{formatMonthLong(point.date)}</p>

      <div className="flex items-baseline gap-3 mt-4 pb-4 border-b border-border">
        <span className="text-2xl font-heading font-bold tabular-nums text-foreground">{formatAUD(point.value)}</span>
        {selectedIndex > 0 && <Delta value={movement} format={formatAUD} />}
      </div>

      <ul className="space-y-4 mt-4 flex-1">
        {changes.length === 0 && (
          <li className="text-sm text-muted-foreground py-6 text-center">
            No changes were recorded this month. The value carried forward unchanged.
          </li>
        )}
        {changes.map((event) => {
          const Icon = event.source === 'advisor' ? UserCog : Sparkles;
          return (
            <li key={event.id} className="flex items-start gap-3 pb-4 border-b border-border last:border-0 last:pb-0">
              <div className="p-1.5 rounded-lg bg-muted flex-shrink-0 mt-0.5">
                <Icon className="w-3.5 h-3.5 text-muted-foreground" aria-hidden="true" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-foreground">{event.label}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {event.driverCode ? `${event.driverCode} · ${VALUE_BUILDER_MODULES[event.driverCode]}` : 'Not driver-attributed'}
                  {' · '}
                  {event.source === 'advisor' ? 'recorded by advisor' : 'calculated by algorithm'}
                </p>
              </div>
              {event.delta !== 0 && (
                <Delta value={event.delta} format={formatAUD} className="text-sm flex-shrink-0" />
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function StepButton({
  label,
  icon: Icon,
  disabled,
  onClick,
}: {
  label: string;
  icon: typeof ChevronLeft;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40 disabled:pointer-events-none"
    >
      <Icon className="w-4 h-4" aria-hidden="true" />
    </button>
  );
}
