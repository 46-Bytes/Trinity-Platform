import { useCallback, useEffect, useState } from 'react';
import { Building2, Gauge, TrendingUp, Wallet } from 'lucide-react';
import { StatCard } from '@/components/ui/stat-card';
import { formatAUDCompact } from '@/lib/utils';
import { getPortfolioValue, type PortfolioValue } from '@/lib/valueDashboardService';
import { EngagementValueTable } from './EngagementValueTable';
import { PortfolioDriverBars } from './PortfolioDriverBars';
import { PortfolioValueChart } from './PortfolioValueChart';
import { DriverStatusPill } from './DriverStatusPill';
import { ErrorState, PageSkeleton, ReadOnlyNotice } from './ValueDashboardChrome';

/**
 * Value roll-up across every engagement. The superadmin entry point.
 */
export function PortfolioOverview() {
  const [portfolio, setPortfolio] = useState<PortfolioValue | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [months, setMonths] = useState(12);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    getPortfolioValue(months)
      .then((data) => {
        if (!cancelled) setPortfolio(data);
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
  }, [months, reloadToken]);

  const retry = useCallback(() => setReloadToken((token) => token + 1), []);

  // Keep the previous data on screen while a range change reloads.
  if (isLoading && !portfolio) return <PageSkeleton />;
  if (error && !portfolio) return <ErrorState message={error} onRetry={retry} />;
  if (!portfolio) return null;

  const movingBackwards = portfolio.businesses.filter((business) => business.upliftAmount < 0).length;
  const weakestDrivers = [...portfolio.driverAverages].sort((a, b) => a.avgScore - b.avgScore).slice(0, 4);

  return (
    <div className="space-y-6">
      <header className="flex items-start gap-4 rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="p-2.5 rounded-xl bg-accent/10 shrink-0">
          <TrendingUp className="w-6 h-6 text-accent" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <h1 className="text-xl font-heading font-bold text-foreground">Value Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Current business value and value uplift across every engagement on the platform.
          </p>
        </div>
      </header>

      <ReadOnlyNotice />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Portfolio Value"
          value={formatAUDCompact(portfolio.totalCurrentValue)}
          change={`from ${formatAUDCompact(portfolio.totalBaselineValue)} at baseline`}
          icon={Wallet}
        />
        <StatCard
          title="Value Uplift"
          value={formatAUDCompact(portfolio.totalUplift)}
          change={`${((portfolio.totalUplift / portfolio.totalBaselineValue) * 100).toFixed(1)}% on baseline`}
          changeType={portfolio.totalUplift >= 0 ? 'positive' : 'negative'}
          icon={TrendingUp}
        />
        <StatCard
          title="Average Uplift"
          value={`${portfolio.avgUpliftPercent.toFixed(1)}%`}
          change={`mean across ${portfolio.businessCount} businesses`}
          icon={Gauge}
        />
        <StatCard
          title="Businesses Tracked"
          value={portfolio.businessCount}
          change={movingBackwards > 0 ? `${movingBackwards} moving backwards` : 'all moving forward'}
          changeType={movingBackwards > 0 ? 'negative' : 'positive'}
          icon={Building2}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <PortfolioValueChart
          className="lg:col-span-2"
          history={portfolio.history}
          baselineTotal={portfolio.totalBaselineValue}
          months={months}
          onMonthsChange={setMonths}
        />

        <section className="card-trinity p-6">
          <h3 className="font-heading font-semibold text-lg text-foreground">Where the Portfolio Needs Work</h3>
          <p className="text-sm text-muted-foreground mt-1 mb-5">
            The weakest value drivers across all engagements.
          </p>
          <ul className="space-y-4">
            {weakestDrivers.map((driver) => (
              <li key={driver.code} className="pb-4 border-b border-border last:border-0 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground">
                      <span className="text-muted-foreground tabular-nums mr-1.5">{driver.code}</span>
                      {driver.name}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {driver.businessesNeedingWork} of {portfolio.businessCount} businesses need work here
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-lg font-heading font-bold tabular-nums text-foreground">
                      {driver.avgScore.toFixed(1)}
                    </p>
                    <DriverStatusPill status={driver.status} className="mt-1" />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <PortfolioDriverBars drivers={portfolio.driverAverages} businessCount={portfolio.businessCount} />

      <EngagementValueTable businesses={portfolio.businesses} />
    </div>
  );
}
