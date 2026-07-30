import { AlertTriangle, ArrowUpRight, TrendingUp, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DRIVER_STATUS_CLASS, DRIVER_STATUS_LABEL, type DriverStatus } from '@/lib/valueDrivers';

const STATUS_ICON: Record<DriverStatus, LucideIcon> = {
  strong: TrendingUp,
  improving: ArrowUpRight,
  needs_work: AlertTriangle,
};

interface DriverStatusPillProps {
  status: DriverStatus;
  className?: string;
}

/**
 * Where a value driver currently sits.
 *
 * Always renders an icon AND a text label alongside the colour. Trinity's
 * success green and destructive red measure only ~5.6 ΔE apart under
 * deuteranopia, so colour alone cannot carry this distinction.
 */
export function DriverStatusPill({ status, className }: DriverStatusPillProps) {
  const Icon = STATUS_ICON[status];
  return (
    <span className={cn(DRIVER_STATUS_CLASS[status], 'whitespace-nowrap', className)}>
      <Icon className="w-3.5 h-3.5 flex-shrink-0" aria-hidden="true" />
      {DRIVER_STATUS_LABEL[status]}
    </span>
  );
}
