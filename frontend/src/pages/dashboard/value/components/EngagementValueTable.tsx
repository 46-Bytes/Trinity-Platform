import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUpDown, ChevronRight, Search } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn, formatAUD } from '@/lib/utils';
import type { BusinessValue, EngagementStatus } from '@/lib/valueDashboardService';
import { formatDate } from '../chartTheme';
import { Delta } from './ValueDashboardChrome';

interface EngagementValueTableProps {
  businesses: BusinessValue[];
}

type SortKey = 'businessName' | 'currentValue' | 'upliftAmount' | 'upliftPercent' | 'driversAtRisk';

const STATUS_CLASS: Record<EngagementStatus, string> = {
  active: 'status-success',
  draft: 'status-info',
  'on-hold': 'status-warning',
  completed: 'status-info',
  cancelled: 'status-error',
};

const STATUS_LABEL: Record<EngagementStatus, string> = {
  active: 'Active',
  draft: 'Draft',
  'on-hold': 'On hold',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

const driversAtRisk = (business: BusinessValue) =>
  business.drivers.filter((driver) => driver.status === 'needs_work').length;

/**
 * Every tracked business, ranked by value movement. Clicking a row opens that
 * business's own value dashboard.
 */
export function EngagementValueTable({ businesses }: EngagementValueTableProps) {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<'all' | EngagementStatus>('all');
  const [sortKey, setSortKey] = useState<SortKey>('upliftPercent');
  const [descending, setDescending] = useState(true);

  const rows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const filtered = businesses.filter((business) => {
      const matchesStatus = status === 'all' || business.engagementStatus === status;
      const matchesSearch =
        !needle ||
        [business.businessName, business.firmName, business.advisorName, business.clientName, business.industry].some(
          (field) => field.toLowerCase().includes(needle),
        );
      return matchesStatus && matchesSearch;
    });

    const value = (business: BusinessValue) =>
      sortKey === 'businessName' ? business.businessName : sortKey === 'driversAtRisk' ? driversAtRisk(business) : business[sortKey];

    return filtered.sort((a, b) => {
      const left = value(a);
      const right = value(b);
      const comparison = typeof left === 'string' ? left.localeCompare(right as string) : (left as number) - (right as number);
      return descending ? -comparison : comparison;
    });
  }, [businesses, search, status, sortKey, descending]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setDescending((previous) => !previous);
      return;
    }
    setSortKey(key);
    setDescending(key !== 'businessName');
  };

  const openBusiness = (engagementId: string) => navigate(`/dashboard/value/${engagementId}`);

  return (
    <section className="card-trinity p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-6">
        <div>
          <h3 className="font-heading font-semibold text-lg text-foreground">Value by Engagement</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Showing {rows.length} of {businesses.length} businesses. Select one to open its dashboard.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search business, firm or advisor"
              aria-label="Search businesses"
              className="input-trinity pl-9 h-9 py-0 sm:w-64"
            />
          </div>
          <Select value={status} onValueChange={(value) => setStatus(value as 'all' | EngagementStatus)}>
            <SelectTrigger className="h-9 w-full sm:w-[150px] bg-background">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent align="end">
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="on-hold">On hold</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="table-trinity">
          <thead>
            <tr>
              <SortableHeader label="Business" sortKey="businessName" active={sortKey} onSort={toggleSort} />
              <th>Status</th>
              <th className="text-right">Baseline</th>
              <SortableHeader label="Current value" sortKey="currentValue" active={sortKey} onSort={toggleSort} align="right" />
              <SortableHeader label="Uplift" sortKey="upliftAmount" active={sortKey} onSort={toggleSort} align="right" />
              <SortableHeader label="Uplift %" sortKey="upliftPercent" active={sortKey} onSort={toggleSort} align="right" />
              <SortableHeader label="Drivers at risk" sortKey="driversAtRisk" active={sortKey} onSort={toggleSort} align="right" />
              <th>Last updated</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {rows.map((business) => (
              <tr
                key={business.engagementId}
                tabIndex={0}
                role="link"
                aria-label={`Open value dashboard for ${business.businessName}`}
                onClick={() => openBusiness(business.engagementId)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openBusiness(business.engagementId);
                  }
                }}
                className="cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
              >
                <td>
                  <div className="font-medium text-foreground">{business.businessName}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {business.firmName} · {business.advisorName}
                  </div>
                </td>
                <td>
                  <span className={STATUS_CLASS[business.engagementStatus]}>
                    {STATUS_LABEL[business.engagementStatus]}
                  </span>
                </td>
                <td className="text-right tabular-nums text-muted-foreground">{formatAUD(business.baselineValue)}</td>
                <td className="text-right tabular-nums font-medium">{formatAUD(business.currentValue)}</td>
                <td className="text-right">
                  <Delta value={business.upliftAmount} format={formatAUD} />
                </td>
                <td className="text-right">
                  <Delta value={business.upliftPercent} format={(value) => `${value.toFixed(1)}%`} hideIcon />
                </td>
                <td className="text-right tabular-nums">
                  <span className={cn(driversAtRisk(business) > 3 && 'text-destructive font-medium')}>
                    {driversAtRisk(business)}
                  </span>
                  <span className="text-muted-foreground"> of {business.drivers.length}</span>
                </td>
                <td>
                  <div className="text-sm">{formatDate(business.lastRecalculatedAt)}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    by {business.lastRecalculatedBy === 'advisor' ? 'advisor' : 'algorithm'}
                  </div>
                </td>
                <td>
                  <ChevronRight className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {rows.length === 0 && (
          <div className="text-center py-12">
            <p className="text-sm text-muted-foreground">No businesses match those filters.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function SortableHeader({
  label,
  sortKey,
  active,
  onSort,
  align = 'left',
}: {
  label: string;
  sortKey: SortKey;
  active: SortKey;
  onSort: (key: SortKey) => void;
  align?: 'left' | 'right';
}) {
  return (
    <th className={align === 'right' ? 'text-right' : undefined}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          'inline-flex items-center gap-1.5 hover:text-foreground transition-colors',
          active === sortKey && 'text-foreground',
        )}
      >
        {label}
        <ArrowUpDown className="w-3 h-3" aria-hidden="true" />
      </button>
    </th>
  );
}
