import { useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowDownRight, ArrowRight, ArrowUpRight, Lock, Shield } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * States and small shared pieces for the Value Dashboard.
 */

/**
 * Makes the spec's integrity rule visible: value figures are written by the
 * uplift algorithm or the assigned advisor, never edited in this UI.
 */
export function ReadOnlyNotice() {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border bg-muted/40 px-4 py-3">
      <Lock className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" aria-hidden="true" />
      <p className="text-sm text-muted-foreground">
        Value figures are produced by the value uplift algorithm and updated by the assigned advisor
        after a re-appraisal or material change. They cannot be edited from this dashboard.
      </p>
    </div>
  );
}

export function AccessDenied() {
  const navigate = useNavigate();
  return (
    <div className="card-trinity p-6">
      <div className="flex flex-col items-center text-center py-12">
        <div className="p-3 rounded-xl bg-destructive/10 mb-4">
          <Shield className="w-6 h-6 text-destructive" aria-hidden="true" />
        </div>
        <p className="text-destructive font-medium mb-2">Access denied</p>
        <p className="text-sm text-muted-foreground max-w-sm">
          You need super admin privileges to view the Value Dashboard.
        </p>
        <Button variant="outline" className="mt-6" onClick={() => navigate('/dashboard')}>
          Back to dashboard
        </Button>
      </div>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card-trinity p-6">
      <div className="flex flex-col items-center text-center py-10">
        <AlertCircle className="w-6 h-6 text-destructive mb-3" aria-hidden="true" />
        <p className="text-destructive font-medium mb-1">Could not load value data</p>
        <p className="text-sm text-muted-foreground max-w-md">{message}</p>
        {onRetry && (
          <Button variant="outline" className="mt-6" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}

/** Placeholder for a chart or panel that has no data to plot yet. */
export function EmptyPanel({ message, className }: { message: string; className?: string }) {
  return (
    <div className={cn('flex items-center justify-center rounded-lg bg-muted/30 h-64', className)}>
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

export function PanelSkeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-xl bg-muted h-72', className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading value dashboard">
      <div className="animate-pulse rounded-xl bg-muted h-24" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse rounded-xl bg-muted h-28" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <PanelSkeleton className="lg:col-span-2" />
        <PanelSkeleton />
      </div>
      <PanelSkeleton className="h-96" />
    </div>
  );
}

interface DeltaProps {
  value: number;
  /** How to render the magnitude. Receives the absolute value. */
  format: (value: number) => string;
  className?: string;
  /** Hides the arrow when the panel already carries directional meaning. */
  hideIcon?: boolean;
}

/**
 * A signed movement. Direction is carried by an arrow and an explicit sign as
 * well as by colour, so it survives a colourblind or greyscale read.
 */
export function Delta({ value, format, className, hideIcon }: DeltaProps) {
  const Icon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : ArrowRight;
  const tone =
    value > 0 ? 'text-success' : value < 0 ? 'text-destructive' : 'text-muted-foreground';
  const sign = value > 0 ? '+' : value < 0 ? '-' : '';

  return (
    <span className={cn('inline-flex items-center gap-1 font-medium tabular-nums', tone, className)}>
      {!hideIcon && <Icon className="w-3.5 h-3.5 flex-shrink-0" aria-hidden="true" />}
      {sign}
      {format(Math.abs(value))}
    </span>
  );
}
