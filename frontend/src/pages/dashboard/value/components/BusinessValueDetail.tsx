import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Gauge, Lock, UserCog, Sparkles } from 'lucide-react';
import { MAX_DRIVER_SCORE } from '@/lib/valueDrivers';
import { getBusinessValue, type BusinessValue } from '@/lib/valueDashboardService';
import { formatAUD } from '@/lib/utils';
import { formatDate } from '../chartTheme';
import { UpliftAttributionBars } from './UpliftAttributionBars';
import { ValueDriversSnapshot } from './ValueDriversSnapshot';
import { ValueMovementLog } from './ValueMovementLog';
import { ValueUpliftChart } from './ValueUpliftChart';
import { Delta, ErrorState, PageSkeleton, ReadOnlyNotice } from './ValueDashboardChrome';

interface BusinessValueDetailProps {
  engagementId: string;
}

/**
 * One business's value dashboard: the headline number, how it has moved, what
 * moved it, and where its value drivers currently sit.
 */
export function BusinessValueDetail({ engagementId }: BusinessValueDetailProps) {
  const [business, setBusiness] = useState<BusinessValue | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    getBusinessValue(engagementId)
      .then((data) => {
        if (cancelled) return;
        setBusiness(data);
        // Open on the most recent movement.
        setSelectedIndex(data.history.length - 1);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Unexpected error loading value data');
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [engagementId, reloadToken]);

  const retry = useCallback(() => setReloadToken((token) => token + 1), []);

  if (isLoading) return <PageSkeleton />;
  if (error) return <ErrorState message={error} onRetry={retry} />;
  if (!business) return null;

  const SourceIcon = business.lastRecalculatedBy === 'advisor' ? UserCog : Sparkles;
  const scoreMovement =
    business.previousOverallScore === null
      ? null
      : Number((business.overallScore - business.previousOverallScore).toFixed(1));

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/dashboard/value"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          All engagements
        </Link>
        <h1 className="text-xl font-heading font-bold text-foreground mt-3">{business.businessName}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {business.firmName} · {business.advisorName} · {business.clientName} · {business.industry}
        </p>
      </div>

      <ReadOnlyNotice />

      <section className="card-trinity p-6 lg:p-8">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 lg:gap-8">
          <div className="lg:col-span-2">
            <p className="text-sm font-medium text-muted-foreground">Current Business Value</p>
            <p className="text-4xl sm:text-5xl font-heading font-bold text-foreground mt-2">
              {formatAUD(business.currentValue)}
            </p>
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 mt-3 text-sm">
              <Delta value={business.upliftAmount} format={formatAUD} />
              <span className="text-muted-foreground">
                since baseline on {formatDate(business.baselineDate)}
              </span>
            </div>
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground mt-4">
              <Lock className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
              Last updated {formatDate(business.lastRecalculatedAt)}
              <SourceIcon className="w-3 h-3 flex-shrink-0 ml-1" aria-hidden="true" />
              by {business.lastRecalculatedBy === 'advisor' ? 'the assigned advisor' : 'the value uplift algorithm'}
            </p>
          </div>

          <dl className="lg:col-span-3 grid grid-cols-1 sm:grid-cols-3 gap-6 lg:border-l lg:border-border lg:pl-8">
            <HeroMetric label="Baseline Value" value={formatAUD(business.baselineValue)} />
            <HeroMetric
              label="Uplift"
              value={`${business.upliftPercent > 0 ? '+' : ''}${business.upliftPercent.toFixed(1)}%`}
              detail={<Delta value={business.upliftAmount} format={formatAUD} className="text-xs" />}
            />
            <HeroMetric
              label="Overall Driver Score"
              value={`${business.overallScore.toFixed(1)} / ${MAX_DRIVER_SCORE}`}
              detail={
                scoreMovement === null ? undefined : (
                  <span className="inline-flex items-center gap-1 text-xs">
                    <Gauge className="w-3 h-3 text-muted-foreground" aria-hidden="true" />
                    <Delta value={scoreMovement} format={(value) => value.toFixed(1)} className="text-xs" hideIcon />
                    <span className="text-muted-foreground">since previous diagnostic</span>
                  </span>
                )
              }
            />
          </dl>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ValueUpliftChart
          history={business.history}
          baselineValue={business.baselineValue}
          selectedIndex={selectedIndex}
          onSelectIndex={setSelectedIndex}
        />
        <ValueMovementLog
          history={business.history}
          selectedIndex={selectedIndex}
          onSelectIndex={setSelectedIndex}
        />
      </div>

      <ValueDriversSnapshot drivers={business.drivers} />

      <UpliftAttributionBars drivers={business.drivers} />
    </div>
  );
}

function HeroMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
      <dd className="text-2xl font-heading font-bold tabular-nums text-foreground mt-1">{value}</dd>
      {detail && <div className="mt-1.5">{detail}</div>}
    </div>
  );
}
