import { useParams } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { AccessDenied, PageSkeleton } from './components/ValueDashboardChrome';
import { PortfolioOverview } from './components/PortfolioOverview';
import { BusinessValueDetail } from './components/BusinessValueDetail';

/**
 * Value / General Dashboard - superadmin only.
 *
 * `/dashboard/value` shows the portfolio roll-up across every engagement;
 * `/dashboard/value/:engagementId` drills into one business. Both live on the
 * same page component so the drill-down is deep-linkable and the browser back
 * button behaves.
 *
 * The gate below is client-side convenience only. When the backend lands, the
 * endpoints must enforce UserRole.SUPER_ADMIN themselves, the way
 * backend/app/api/dashboard.py already does for /activity.
 */
export default function ValueDashboardPage() {
  const { engagementId } = useParams<{ engagementId: string }>();
  const { user, isLoading: authLoading } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';

  // Wait for the session before judging the role, otherwise a hard refresh
  // flashes "Access denied" while `user` is still null.
  if (authLoading) return <PageSkeleton />;
  if (!isSuperAdmin) return <AccessDenied />;

  return engagementId ? <BusinessValueDetail engagementId={engagementId} /> : <PortfolioOverview />;
}
