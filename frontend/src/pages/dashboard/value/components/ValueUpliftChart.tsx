import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ValuePoint } from '@/lib/valueDashboardService';
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

interface ValueUpliftChartProps {
  history: ValuePoint[];
  baselineValue: number;
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
}

/**
 * Business value since baseline. Every point is a recorded movement, and
 * selecting one drives the movement log beside it - this is the spec's
 * requirement that each movement links back to the change that caused it.
 */
export function ValueUpliftChart({ history, baselineValue, selectedIndex, onSelectIndex }: ValueUpliftChartProps) {
  const selected = history[selectedIndex];

  const table = (
    <div className="overflow-x-auto">
      <table className="table-trinity">
        <thead>
          <tr>
            <th>Month</th>
            <th className="text-right">Value</th>
            <th className="text-right">Movement</th>
            <th>Changes recorded</th>
          </tr>
        </thead>
        <tbody>
          {history.map((point, index) => {
            const movement = index === 0 ? 0 : point.value - history[index - 1].value;
            const changes = point.events.filter((event) => event.delta !== 0);
            return (
              <tr key={point.date}>
                <td>{formatMonthLong(point.date)}</td>
                <td className="text-right tabular-nums">{formatAUD(point.value)}</td>
                <td className="text-right tabular-nums text-muted-foreground">
                  {index === 0 ? '—' : formatAUDDelta(movement)}
                </td>
                <td className="text-muted-foreground">
                  {changes.length > 0 ? changes.map((event) => event.label).join('; ') : 'No changes recorded'}
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
      title="Value Uplift Over Time"
      description="Select a point to see the changes that moved the value."
      table={table}
      className="lg:col-span-2"
    >
      {history.length < 2 ? (
        <EmptyPanel message="No value movement recorded yet." className="h-72" />
      ) : (
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={history}
              margin={{ top: 16, right: 28, left: 4, bottom: 4 }}
              onClick={(state: { activeTooltipIndex?: number } | undefined) => {
                if (state && typeof state.activeTooltipIndex === 'number') onSelectIndex(state.activeTooltipIndex);
              }}
              style={{ cursor: 'pointer' }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} vertical={false} />
              <XAxis dataKey="date" stroke={CHART_GRID} tick={axisTick} tickFormatter={formatMonthTick} tickMargin={8} />
              <YAxis
                stroke={CHART_GRID}
                tick={axisTick}
                tickFormatter={formatAUDCompact}
                width={72}
                domain={['dataMin - 200000', 'dataMax + 200000']}
              />
              <Tooltip
                contentStyle={tooltipContentStyle}
                cursor={tooltipCursor}
                labelFormatter={(label) => formatMonthLong(String(label))}
                formatter={(value: number) => [formatAUD(value), 'Business value']}
              />
              <ReferenceLine
                y={baselineValue}
                stroke="hsl(var(--muted-foreground))"
                strokeDasharray="4 4"
                label={{
                  value: `Baseline ${formatAUDCompact(baselineValue)}`,
                  position: 'insideBottomLeft',
                  fill: 'hsl(var(--muted-foreground))',
                  fontSize: 11,
                }}
              />
              <Line
                type="monotone"
                dataKey="value"
                name="Business value"
                stroke={CHART_SERIES}
                strokeWidth={2}
                dot={{ r: 4, strokeWidth: 0, fill: CHART_SERIES }}
                activeDot={{ r: 7, strokeWidth: 2, stroke: 'hsl(var(--card))' }}
              />
              {selected && (
                <ReferenceDot
                  x={selected.date}
                  y={selected.value}
                  r={7}
                  isFront
                  fill={CHART_SERIES}
                  stroke="hsl(var(--card))"
                  strokeWidth={2}
                  label={{
                    value: formatAUDCompact(selected.value),
                    position: 'top',
                    fill: 'hsl(var(--foreground))',
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </ChartPanel>
  );
}
