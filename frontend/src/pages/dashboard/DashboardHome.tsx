import { useAuth } from '@/context/AuthContext';
import { Clock } from 'lucide-react';
import { SuperAdminDashboard } from './components/SuperAdminDashboard';
import { AdvisorDashboard } from './components/AdvisorDashboard';
import { ClientDashboard } from './components/ClientDashboard';
import { AdminDashboard } from './components/AdminDashboard';
import { FirmAdminDashboard } from './components/FirmAdminDashboard';
import { OwnerProgramCard } from './components/OwnerProgramCard';
import { isBusinessOwner } from '@/types/auth';

// Role-specific dashboard components are now in separate files

export default function DashboardHome() {
  const { user } = useAuth();
  const owner = isBusinessOwner(user);

  const getDashboardTitle = () => {
    if (owner) return 'My Business';
    switch (user?.role) {
      case 'super_admin': return 'Platform Overview';
      case 'admin': return 'Administration Dashboard';
      case 'advisor': return 'Advisor Dashboard';
      case 'client': return 'My Dashboard';
      case 'firm_admin': return 'Firm Dashboard';
      case 'firm_advisor': return 'Advisor Dashboard';
      case 'team_member': return 'My Work';
      default: return 'Dashboard';
    }
  };

  const renderDashboard = () => {
    switch (user?.role) {
      case 'super_admin': return <SuperAdminDashboard />;
      case 'admin': return <AdminDashboard />;
      case 'advisor':
      case 'firm_advisor': return <AdvisorDashboard />;
      // A self-service business owner is a `client`, so the same dashboard
      // serves both - the owner just gets a program card above it.
      case 'client':
      case 'team_member': return <ClientDashboard />;
      case 'firm_admin': return <FirmAdminDashboard />;
      default: return null;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">
            {getDashboardTitle()}
          </h1>
          <p className="text-muted-foreground mt-1">
            Welcome back, {user?.name.split(' ')[0]}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="w-4 h-4" />
          Last updated: Just now
        </div>
      </div>

      {owner && <OwnerProgramCard />}

      {renderDashboard()}
    </div>
  );
}
