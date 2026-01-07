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
import UsersPage from "./pages/dashboard/UsersPage";
import ClientsPage from "./pages/dashboard/ClientsPage";
import AdvisorsPage from "./pages/dashboard/AdvisorsPage";
import EngagementsPage from "./pages/dashboard/Engagement/EngagementsPage";
import EngagementDetailPage from "./pages/dashboard/Engagement/EngagementDetailPage";
import TasksPage from "./pages/dashboard/TasksPage";
import DocumentsPage from "./pages/dashboard/DocumentsPage";
import AIToolsPage from "./pages/dashboard/AIToolsPage";
import SettingsPage from "./pages/dashboard/SettingsPage";
import FirmsPage from "./pages/dashboard/Firms";
import SubscriptionsPage from "./pages/dashboard/Subscriptions";

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
        <Route path="clients" element={<ClientsPage />} />
        <Route path="advisors" element={<AdvisorsPage />} />
        <Route path="engagements" element={<EngagementsPage />} />
        <Route path="engagements/:engagementId" element={<EngagementDetailPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="ai-tools" element={<AIToolsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="firms" element={<FirmsPage />} />
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
