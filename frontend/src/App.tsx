import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Provider } from "react-redux";
import { store } from "@/store";
import { AuthProvider, useAuth } from "@/context/AuthContext";

// Pages
import Index from "./pages/Index";
import Login from "./pages/Login";
import AuthCallback from "./pages/AuthCallback";
import VerifyEmail from "./pages/VerifyEmail";
import NotFound from "./pages/NotFound";

// Dashboard
import { DashboardLayout } from "./components/layout/DashboardLayout";
import DashboardHome from "./pages/dashboard/DashboardHome";
import UsersPage from "./pages/dashboard/users/UsersPage";
import UserDetailPage from "./pages/dashboard/users/details/UserDetailPage";
import ClientsPage from "./pages/dashboard/ClientsPage";
import AdvisorsPage from "./pages/dashboard/AdvisorsPage";
import EngagementsPage from "./pages/dashboard/Engagement/EngagementsPage";
import EngagementDetailPage from "./pages/dashboard/Engagement/EngagementDetailPage";
import TasksPage from "./pages/dashboard/TasksPage";
import DocumentsPage from "./pages/dashboard/DocumentsPage";
import AIToolsPage from "./pages/dashboard/AIToolsPage";
import SettingsPage from "./pages/dashboard/SettingsPage";
import FirmsPage from "./pages/dashboard/firm/Firms";
import FirmDetailsLayout from "./pages/dashboard/firm/firmDetails/FirmDetailsLayout";
import FirmDetailsAdvisors from "./pages/dashboard/firm/firmDetails/FirmDetailsAdvisors";
import FirmDetailsClients from "./pages/dashboard/firm/firmDetails/FirmDetailsClients";
import FirmDetailsEngagements from "./pages/dashboard/firm/firmDetails/FirmDetailsEngagements";
import FirmDetailsTasks from "./pages/dashboard/firm/firmDetails/FirmDetailsTasks";
import FirmDetailsSubscription from "./pages/dashboard/firm/firmDetails/FirmDetailsSubscription";
import SubscriptionsPage from "./pages/dashboard/Subscriptions";
import FileUploadPOCPage from "./pages/poc/FileUploadPOCPage";
import StrategyWorkbookPage from "./pages/dashboard/StrategyWorkbookPage";
import StrategicBusinessPlanPage from "./pages/dashboard/StrategicBusinessPlanPage";
import AIPrivacyPage from "./pages/dashboard/AIPrivacyPage";
import TeamPage from "./pages/dashboard/TeamPage";
import BillingPage from "./pages/dashboard/BillingPage";

// Self-service (SaaS) signup funnel
import SignUpPage from "./pages/signup/SignUpPage";
import CheckoutPage from "./pages/signup/CheckoutPage";
import OnboardingCompletePage from "./pages/signup/OnboardingCompletePage";

import { isBusinessOwner, type UserRole } from "@/types/auth";

const queryClient = new QueryClient();

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div className="flex items-center justify-center min-h-screen">Checking authentication...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

/**
 * Restrict a route to specific roles.
 *
 * `ProtectedRoute` only checks that somebody is signed in, so without this any
 * authenticated user could reach any dashboard page by typing its URL.
 */
function RoleGuard({ roles, children }: { roles: UserRole[]; children: React.ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) return null;

  if (!user || !roles.includes(user.role)) {
    return (
      <div className="card-trinity p-6">
        <div className="text-center py-12">
          <p className="text-destructive mb-2">Access Denied</p>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view this page.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

/** Restrict a route to self-service business owners (billing, team management). */
function OwnerGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) return null;

  if (!isBusinessOwner(user)) {
    return (
      <div className="card-trinity p-6">
        <div className="text-center py-12">
          <p className="text-destructive mb-2">Access Denied</p>
          <p className="text-sm text-muted-foreground">
            This area is only available to self-service business owners.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Index />} />
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/verify-email" element={<VerifyEmail />} />

      {/* Self-service (SaaS) signup funnel - Feature 7 */}
      <Route path="/signup" element={<SignUpPage />} />
      <Route path="/onboarding/checkout" element={
        <ProtectedRoute>
          <OwnerGuard><CheckoutPage /></OwnerGuard>
        </ProtectedRoute>
      } />
      <Route path="/onboarding/complete" element={
        <ProtectedRoute>
          <OwnerGuard><OnboardingCompletePage /></OwnerGuard>
        </ProtectedRoute>
      } />

      {/* Protected Dashboard Routes */}
      <Route path="/dashboard" element={
        <ProtectedRoute>
          <DashboardLayout />
        </ProtectedRoute>
      }>
        <Route index element={<DashboardHome />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="users/:id" element={<UserDetailPage />} />
        <Route path="clients" element={<ClientsPage />} />
        <Route path="advisors" element={<AdvisorsPage />} />
        <Route path="engagements" element={<EngagementsPage />} />
        <Route path="engagements/:engagementId" element={<EngagementDetailPage />} />
        <Route path="engagements/:engagementId/bba" element={<FileUploadPOCPage />} />
        <Route path="engagements/:engagementId/strategy-workbook" element={<StrategyWorkbookPage />} />
        <Route path="engagements/:engagementId/strategic-business-plan" element={<StrategicBusinessPlanPage />} />
        <Route path="ai-tools/bba" element={<FileUploadPOCPage />} />
        <Route path="ai-tools/strategy-workbook" element={<StrategyWorkbookPage />} />
        <Route path="ai-tools/strategic-business-plan" element={<StrategicBusinessPlanPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="ai-tools" element={<AIToolsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="firms" element={<FirmsPage />} />
        <Route path="firms/:firmId" element={<FirmDetailsLayout />}>
          <Route path="clients" element={<FirmDetailsClients />} />
          <Route path="advisors" element={<FirmDetailsAdvisors />} />
          <Route path="engagements" element={<FirmDetailsEngagements />} />
          <Route path="tasks" element={<FirmDetailsTasks />} />
          <Route path="subscription" element={<FirmDetailsSubscription />} />
        </Route>
        <Route path="subscriptions" element={<SubscriptionsPage />} />
        <Route path="ai-privacy" element={<AIPrivacyPage />} />
        {/* Self-service business owner surfaces - Feature 7 */}
        <Route path="team" element={<OwnerGuard><TeamPage /></OwnerGuard>} />
        <Route path="billing" element={<OwnerGuard><BillingPage /></OwnerGuard>} />
        {/* Placeholder routes */}
        <Route path="chat" element={<DashboardHome />} />
        <Route path="analytics" element={<DashboardHome />} />
        <Route path="firm" element={<DashboardHome />} />
        <Route path="security" element={<DashboardHome />} />
      </Route>
      
      
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

const App = () => (
  <Provider store={store}>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>
  </Provider>
);

export default App;
