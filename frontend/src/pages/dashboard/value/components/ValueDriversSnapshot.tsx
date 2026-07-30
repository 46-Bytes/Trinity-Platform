import { useState } from 'react';
import { MAX_DRIVER_SCORE } from '@/lib/valueDrivers';
import type { ValueDriver } from '@/lib/valueDashboardService';
import { cn, formatAUD } from '@/lib/utils';
import { Delta } from './ValueDashboardChrome';
import { DriverStatusPill } from './DriverStatusPill';

interface ValueDriversSnapshotProps {
  drivers: ValueDriver[];
}

type Order = 'weakest' | 'module';

/**
 * Where each of the eleven value drivers currently sits for this business.
 *
 * Meters rather than a chart: eleven labelled rows with a score, a movement and
 * a state read better as a list than as eleven bars, and the meter track is the
 * existing progress-trinity component.
 */
export function ValueDriversSnapshot({ drivers }: ValueDriversSnapshotProps) {
  const [order, setOrder] = useState<Order>('weakest');

  const sorted =
    order === 'weakest'
      ? [...drivers].sort((a, b) => a.score - b.score)
      : [...drivers].sort((a, b) => Number(a.code.slice(1)) - Number(b.code.slice(1)));

  return (
    <section className="card-trinity p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-6">
        <div>
          <h3 className="font-heading font-semibold text-lg text-foreground">Value Drivers Snapshot</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Diagnostic score out of {MAX_DRIVER_SCORE}, with movement since the previous diagnostic.
          </p>
        </div>
        <div className="flex items-center rounded-lg border border-border p-0.5 flex-shrink-0" role="group" aria-label="Driver order">
          <OrderButton active={order === 'weakest'} onClick={() => setOrder('weakest')} label="Weakest first" />
          <OrderButton active={order === 'module'} onClick={() => setOrder('module')} label="Module order" />
        </div>
      </div>

      <ul className="space-y-5">
        {sorted.map((driver) => (
          <li key={driver.code}>
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 mb-2">
              <p className="text-sm font-medium text-foreground min-w-0">
                <span className="text-muted-foreground tabular-nums mr-2">{driver.code}</span>
                {driver.name}
              </p>
              <div className="flex items-center gap-3 flex-shrink-0">
                {driver.valueContribution !== 0 && (
                  <span className="text-xs text-muted-foreground tabular-nums hidden sm:inline">
                    {formatAUD(driver.valueContribution)} attributed
                  </span>
                )}
                {driver.delta !== null && driver.delta !== 0 && (
                  <Delta value={driver.delta} format={(value) => value.toFixed(1)} className="text-xs" />
                )}
                <span className="text-sm font-heading font-bold tabular-nums text-foreground">
                  {driver.score.toFixed(1)}
                </span>
                <DriverStatusPill status={driver.status} />
              </div>
            </div>
            <div
              className="progress-trinity"
              role="img"
              aria-label={`${driver.name}: ${driver.score.toFixed(1)} out of ${MAX_DRIVER_SCORE}`}
            >
              <div
                className="progress-trinity-bar"
                style={{ width: `${(driver.score / MAX_DRIVER_SCORE) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function OrderButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors',
        active ? 'bg-accent/10 text-accent' : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
      )}
    >
      {label}
    </button>
  );
}
