import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { MAX_DRIVER_SCORE } from '@/lib/valueDrivers';
import type { PortfolioDriverAverage } from '@/lib/valueDashboardService';
import { CHART_GRID, CHART_SERIES, axisTick, tooltipBarCursor, tooltipContentStyle } from '../chartTheme';
import { ChartPanel } from './ChartPanel';
import { Delta } from './ValueDashboardChrome';
import { DriverStatusPill } from './DriverStatusPill';

interface PortfolioDriverBarsProps {
  drivers: PortfolioDriverAverage[];
  businessCount: number;
}

const truncate = (value: string, max = 26) => (value.length > max ? `${value.slice(0, max - 1)}…` : value);

/**
 * Average score for each of the eleven Value Builder drivers across the portfolio.
 *
 * Magnitude is carried by bar length alone - the bars are one flat teal rather
 * than a shaded ramp, because colouring by the same quantity the length already
 * encodes adds no information (and teal tints fail the contrast floor against
 * the card surface anyway).
 */
export function PortfolioDriverBars({ drivers, businessCount }: PortfolioDriverBarsProps) {
  const sorted = [...drivers].sort((a, b) => a.avgScore - b.avgScore);
  const data = sorted.map((driver) => ({ ...driver, label: `${driver.code} · ${driver.name}` }));

  const table = (
    <div className="overflow-x-auto">
      <table className="table-trinity">
        <thead>
          <tr>
            <th>Value driver</th>
            <th className="text-right">Average score</th>
            <th className="text-right">Movement</th>
            <th>Status</th>
            <th className="text-right">Businesses needing work</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((driver) => (
            <tr key={driver.code}>
              <td>
                <span className="text-muted-foreground tabular-nums mr-2">{driver.code}</span>
                {driver.name}
              </td>
              <td className="text-right tabular-nums">{driver.avgScore.toFixed(1)} / 5</td>
              <td className="text-right">
                <Delta
                  value={Number((driver.avgScore - driver.avgPreviousScore).toFixed(1))}
                  format={(v) => v.toFixed(1)}
                />
              </td>
              <td>
                <DriverStatusPill status={driver.status} />
              </td>
              <td className="text-right tabular-nums">
                {driver.businessesNeedingWork} of {businessCount}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <ChartPanel
      title="Value Drivers Across the Portfolio"
      description="Average diagnostic score per driver, 0–5, weakest first."
      table={table}
    >
      <div className="h-[420px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, left: 4, bottom: 4 }} barCategoryGap={6}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
            <XAxis
              type="number"
              domain={[0, MAX_DRIVER_SCORE]}
              ticks={[0, 1, 2, 3, 4, 5]}
              stroke={CHART_GRID}
              tick={axisTick}
            />
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
              formatter={(value: number) => [`${value.toFixed(1)} / 5`, 'Average score']}
            />
            <Bar dataKey="avgScore" name="Average score" fill={CHART_SERIES} radius={[0, 4, 4, 0]} maxBarSize={20}>
              <LabelList
                dataKey="avgScore"
                position="right"
                fill="hsl(var(--foreground))"
                fontSize={12}
                formatter={(value: number) => value.toFixed(1)}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartPanel>
  );
}
