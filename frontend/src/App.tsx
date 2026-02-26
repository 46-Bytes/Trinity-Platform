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

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Index />} />
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      
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
        <Route path="strategy-workbook" element={<StrategyWorkbookPage />} />
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
