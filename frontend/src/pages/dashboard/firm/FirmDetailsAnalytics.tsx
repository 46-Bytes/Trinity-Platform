// Wrapper component that shows Analytics/Dashboard for a specific firm (superadmin view)
// Reuses the FirmAdminDashboard logic from DashboardHome
import { useOutletContext } from 'react-router-dom';
import DashboardHome from '@/pages/dashboard/DashboardHome';

interface FirmDetailsContext {
  firmId: string;
}

export default function FirmDetailsAnalytics() {
  const { firmId } = useOutletContext<FirmDetailsContext>();
  
  // The DashboardHome will show FirmAdminDashboard when user role is firm_admin
  // For superadmin viewing a firm, we want the same view
  // The firm is already set in Redux state from the layout
  return <DashboardHome />;
}

