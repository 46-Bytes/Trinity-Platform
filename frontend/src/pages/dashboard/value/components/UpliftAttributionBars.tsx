import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { ValueDriver } from '@/lib/valueDashboardService';
import { formatAUD, formatAUDCompact } from '@/lib/utils';
import { CHART_GRID, CHART_SERIES, axisTick, tooltipBarCursor, tooltipContentStyle } from '../chartTheme';
import { ChartPanel } from './ChartPanel';
import { EmptyPanel } from './ValueDashboardChrome';

interface UpliftAttributionBarsProps {
  drivers: ValueDriver[];
}

const truncate = (value: string, max = 26) => (value.length > max ? `${value.slice(0, max - 1)}…` : value);

/**
 * How much of this business's uplift the algorithm attributes to each driver.
 *
 * Answers "which work actually moved the number". Advisor re-appraisals are not
 * driver-attributed and so do not appear here - the total below the chart says
 * so explicitly rather than leaving the reader to wonder why the bars do not sum
 * to the headline uplift.
 */
export function UpliftAttributionBars({ drivers }: UpliftAttributionBarsProps) {
  const contributing = drivers
    .filter((driver) => driver.valueContribution !== 0)
    .sort((a, b) => b.valueContribution - a.valueContribution)
    .map((driver) => ({ ...driver, label: `${driver.code} · ${driver.name}` }));

  const attributedTotal = contributing.reduce((sum, driver) => sum + driver.valueContribution, 0);

  const table = (
    <div className="overflow-x-auto">
      <table className="table-trinity">
        <thead>
          <tr>
            <th>Value driver</th>
            <th className="text-right">Attributed uplift</th>
          </tr>
        </thead>
        <tbody>
          {contributing.map((driver) => (
            <tr key={driver.code}>
              <td>
                <span className="text-muted-foreground tabular-nums mr-2">{driver.code}</span>
                {driver.name}
              </td>
              <td className="text-right tabular-nums">{formatAUD(driver.valueContribution)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <ChartPanel
      title="Uplift Attribution by Driver"
      description={`${formatAUD(attributedTotal)} of movement attributed to value drivers. Advisor re-appraisals are counted separately.`}
      table={contributing.length > 0 ? table : undefined}
    >
      {contributing.length === 0 ? (
        <EmptyPanel message="No driver-attributed uplift recorded yet." />
      ) : (
        <div style={{ height: Math.max(180, contributing.length * 34 + 40) }} className="w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={contributing}
              layout="vertical"
              margin={{ top: 4, right: 24, left: 4, bottom: 4 }}
              barCategoryGap={6}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
              <XAxis type="number" stroke={CHART_GRID} tick={axisTick} tickFormatter={formatAUDCompact} />
              <YAxis
                type="category"
                dataKey="label"
                width={190}
                stroke={CHART_GRID}
                tick={axisTick}
                tickFormatter={(value: string) => truncate(value)}
                tickLine={false}
              />
              <Tooltip
                contentStyle={tooltipContentStyle}
                cursor={tooltipBarCursor}
                formatter={(value: number) => [formatAUD(value), 'Attributed uplift']}
              />
              <ReferenceLine x={0} stroke={CHART_GRID} />
              <Bar dataKey="valueContribution" name="Attributed uplift" fill={CHART_SERIES} radius={[0, 4, 4, 0]} maxBarSize={20} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </ChartPanel>
  );
}
