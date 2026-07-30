/**
 * Shared chart chrome for the Value Dashboard.
 *
 * Every value in here is a Trinity CSS token, never a raw hex, so the charts
 * follow the design system and a future dark-mode toggle needs no changes here.
 *
 * Colour policy for this dashboard: there is exactly ONE series colour, the
 * Trinity accent teal. It is the only palette entry that clears 3:1 on the card
 * surface, and Trinity's --success sits only ~5.8 ΔE from it, so the two can
 * never be used as distinguishable series. Every chart here is one teal series
 * against grey context; magnitude is carried by bar length and line position,
 * never by shading the series.
 */

/** The single series colour. Trinity --accent, 3.22:1 on the white card. */
export const CHART_SERIES = 'hsl(var(--accent))';

/** Recessive chrome. */
export const CHART_GRID = 'hsl(var(--border))';
export const CHART_AXIS = 'hsl(var(--muted-foreground))';
export const CHART_SURFACE = 'hsl(var(--card))';

export const axisTick = { fill: CHART_AXIS, fontSize: 12 } as const;

export const tooltipContentStyle = {
  backgroundColor: CHART_SURFACE,
  border: '1px solid hsl(var(--border))',
  borderRadius: '8px',
  boxShadow: 'var(--shadow-md)',
  fontSize: '12px',
} as const;

export const tooltipCursor = { stroke: CHART_AXIS, strokeWidth: 1, strokeDasharray: '3 3' } as const;

export const tooltipBarCursor = { fill: 'hsl(var(--muted) / 0.5)' } as const;

/** Formats an ISO month to "Aug 25" for axis ticks. */
export function formatMonthTick(iso: string): string {
  return new Date(iso).toLocaleDateString('en-AU', { month: 'short', year: '2-digit' });
}

/** Formats an ISO date to "August 2025" for tooltip and panel headings. */
export function formatMonthLong(iso: string): string {
  return new Date(iso).toLocaleDateString('en-AU', { month: 'long', year: 'numeric' });
}

/** Formats an ISO date to "1 Aug 2025". */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
}
