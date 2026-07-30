import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { formatAUD, formatAUDCompact, formatAUDDelta } from '@/lib/utils';
import {
  CHART_GRID,
  CHART_SERIES,
  axisTick,
  formatMonthLong,
  formatMonthTick,
  tooltipContentStyle,
  tooltipCursor,
} from '../chartTheme';
import { ChartPanel } from './ChartPanel';
import { EmptyPanel } from './ValueDashboardChrome';

interface PortfolioValueChartProps {
  history: Array<{ date: string; totalValue: number }>;
  /** Combined baseline value of every business, for the reference line. */
  baselineTotal: number;
  months: number;
  onMonthsChange: (months: number) => void;
  className?: string;
}

/**
 * Total portfolio value over time.
 *
 * One series against a dashed baseline - the reader's job is "how far above the
 * starting point are we", which is emphasis, not category comparison. A single
 * series needs no legend; the panel title names it.
 */
export function PortfolioValueChart({
  history,
  baselineTotal,
  months,
  onMonthsChange,
  className,
}: PortfolioValueChartProps) {
  const latest = history[history.length - 1];

  const rangePicker = (
    <Select value={String(months)} onValueChange={(value) => onMonthsChange(Number(value))}>
      <SelectTrigger className="h-9 w-[150px] bg-background">
        <SelectValue placeholder="Time period" />
      </SelectTrigger>
      <SelectContent align="end">
        <SelectItem value="6">Last 6 months</SelectItem>
        <SelectItem value="12">Last 12 months</SelectItem>
        <SelectItem value="0">All time</SelectItem>
      </SelectContent>
    </Select>
  );

  const table = (
    <div className="overflow-x-auto">
      <table className="table-trinity">
        <thead>
          <tr>
            <th>Month</th>
            <th className="text-right">Portfolio value</th>
            <th className="text-right">Movement</th>
          </tr>
        </thead>
        <tbody>
          {history.map((point, index) => {
            const movement = index === 0 ? 0 : point.totalValue - history[index - 1].totalValue;
            return (
              <tr key={point.date}>
                <td>{formatMonthLong(point.date)}</td>
                <td className="text-right tabular-nums">{formatAUD(point.totalValue)}</td>
                <td className="text-right tabular-nums text-muted-foreground">
                  {index === 0 ? '—' : formatAUDDelta(movement)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  return (
    <ChartPanel
      title="Portfolio Value Over Time"
      description="Combined current value of every tracked business, against the combined baseline."
      action={rangePicker}
      table={table}
      className={className}
    >
      {history.length < 2 ? (
        <EmptyPanel message="Not enough history to plot a trend yet." className="h-72" />
      ) : (
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={history} margin={{ top: 16, right: 28, left: 4, bottom: 4 }}>
              <defs>
                <linearGradient id="portfolioValueFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART_SERIES} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={CHART_SERIES} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} vertical={false} />
              <XAxis dataKey="date" stroke={CHART_GRID} tick={axisTick} tickFormatter={formatMonthTick} tickMargin={8} />
              <YAxis
                stroke={CHART_GRID}
                tick={axisTick}
                tickFormatter={formatAUDCompact}
                width={72}
                domain={['dataMin - 2000000', 'dataMax + 2000000']}
              />
              <Tooltip
                contentStyle={tooltipContentStyle}
                cursor={tooltipCursor}
                labelFormatter={(label) => formatMonthLong(String(label))}
                formatter={(value: number) => [formatAUD(value), 'Portfolio value']}
              />
              <ReferenceLine
                y={baselineTotal}
                stroke="hsl(var(--muted-foreground))"
                strokeDasharray="4 4"
                label={{
                  value: `Baseline ${formatAUDCompact(baselineTotal)}`,
                  position: 'insideBottomLeft',
                  fill: 'hsl(var(--muted-foreground))',
                  fontSize: 11,
                }}
              />
              <Area
                type="monotone"
                dataKey="totalValue"
                name="Portfolio value"
                stroke={CHART_SERIES}
                strokeWidth={2}
                fill="url(#portfolioValueFill)"
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2, stroke: 'hsl(var(--card))' }}
              />
              <ReferenceDot
                x={latest.date}
                y={latest.totalValue}
                r={0}
                isFront
                label={{
                  value: formatAUDCompact(latest.totalValue),
                  position: 'top',
                  fill: 'hsl(var(--foreground))',
                  fontSize: 12,
                  fontWeight: 600,
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </ChartPanel>
  );
}
