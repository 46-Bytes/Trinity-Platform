import { useState, type ReactNode } from 'react';
import { BarChart3, Table2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChartPanelProps {
  title: string;
  description?: string;
  /** Rendered at the right of the header row, e.g. a range Select. */
  action?: ReactNode;
  /**
   * The same data as a table. Supplying it adds a Chart/Table switch - the
   * accessibility relief for readers who cannot use the plotted colours.
   */
  table?: ReactNode;
  className?: string;
  children: ReactNode;
}

/**
 * Card shell shared by every chart on the Value Dashboard: title, optional
 * control, and an optional table view of the same numbers.
 */
export function ChartPanel({ title, description, action, table, className, children }: ChartPanelProps) {
  const [view, setView] = useState<'chart' | 'table'>('chart');

  return (
    <section className={cn('card-trinity p-6', className)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-6">
        <div className="min-w-0">
          <h3 className="font-heading font-semibold text-lg text-foreground">{title}</h3>
          {description && <p className="text-sm text-muted-foreground mt-1">{description}</p>}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {action}
          {table && (
            <div className="flex items-center rounded-lg border border-border p-0.5" role="group" aria-label={`${title} view`}>
              <ViewButton
                active={view === 'chart'}
                onClick={() => setView('chart')}
                icon={BarChart3}
                label="Chart"
              />
              <ViewButton
                active={view === 'table'}
                onClick={() => setView('table')}
                icon={Table2}
                label="Table"
              />
            </div>
          )}
        </div>
      </div>
      {view === 'chart' || !table ? children : table}
    </section>
  );
}

function ViewButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof BarChart3;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors',
        active ? 'bg-accent/10 text-accent' : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
      )}
    >
      <Icon className="w-3.5 h-3.5" aria-hidden="true" />
      {label}
    </button>
  );
}
