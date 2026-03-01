import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { BillingProvider, useBilling } from './contexts/BillingContext';
import { IdentityProvider } from './contexts/IdentityContext';
import { setPaywallCallback } from './services/api';
import { Toaster } from './components/ui/sonner';
import TrialBanner from './components/TrialBanner';
import CompleteAccountBanner from './components/CompleteAccountBanner';
import CompleteAccountModal from './components/CompleteAccountModal';
import PaywallModal from './components/PaywallModal';
import './App.css';
import './index.css';

import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import RegisterManagementPage from './pages/RegisterManagementPage';
import OnboardingPage from './pages/OnboardingPage';
import PendingApprovalPage from './pages/PendingApprovalPage';
import JoinRequestsPage from './pages/JoinRequestsPage';
import TaskDetailPage from './pages/TaskDetailPage';
import AdminPage from './pages/AdminPage';
import AdminBillingPage from './pages/AdminBillingPage';
import OrgBillingPage from './pages/OrgBillingPage';
import AdminUsersPage from './pages/AdminUsersPage';
import ProjectControlPage from './pages/ProjectControlPage';
import UnitDetailPage from './pages/UnitDetailPage';
import UnitHomePage from './pages/UnitHomePage';
import UnitPlansPage from './pages/UnitPlansPage';
import ProjectTasksPage from './pages/ProjectTasksPage';
import ProjectPlansPage from './pages/ProjectPlansPage';
import MyProjectsPage from './pages/MyProjectsPage';
import WaLoginPage from './pages/WaLoginPage';
import OwnershipTransferPage from './pages/OwnershipTransferPage';
import ProjectDashboardPage from './pages/ProjectDashboardPage';
import FloorDetailPage from './pages/FloorDetailPage';
import StageDetailPage from './pages/StageDetailPage';
import QCFloorSelectionPage from './pages/QCFloorSelectionPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import AccountSettingsPage from './pages/AccountSettingsPage';

const INTENDED_PATH_KEY = 'intendedPath';

const ProtectedRoute = ({ children, allowedRoles, requireSuperAdmin }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-500"></div>
      </div>
    );
  }

  if (!user) {
    const currentPath = location.pathname + location.search;
    if (currentPath && currentPath !== '/' && currentPath !== '/login' && currentPath !== '/projects') {
      sessionStorage.setItem(INTENDED_PATH_KEY, currentPath);
    }
    return <Navigate to="/login" replace />;
  }

  if (user.user_status === 'pending_pm_approval' || user.user_status === 'pending') {
    return <Navigate to="/pending" replace />;
  }

  if (requireSuperAdmin && user.platform_role !== 'super_admin') {
    return <Navigate to="/projects" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/projects" replace />;
  }

  return children;
};

const PaywallConnector = () => {
  const { setShowPaywall } = useBilling();
  useEffect(() => {
    setPaywallCallback(() => setShowPaywall(true));
    return () => setPaywallCallback(null);
  }, [setShowPaywall]);
  return null;
};

const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/phone-login" element={<Navigate to="/login" replace />} />
      <Route path="/auth/wa" element={<WaLoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/register-management" element={<RegisterManagementPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route
        path="/settings/account"
        element={
          <ProtectedRoute>
            <AccountSettingsPage />
          </ProtectedRoute>
        }
      />
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route path="/pending" element={<PendingApprovalPage />} />
      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <MyProjectsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute requireSuperAdmin>
            <AdminPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/billing"
        element={
          <ProtectedRoute requireSuperAdmin>
            <AdminBillingPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/billing/org/:orgId"
        element={
          <ProtectedRoute>
            <OrgBillingPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users"
        element={
          <ProtectedRoute requireSuperAdmin>
            <AdminUsersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/join-requests"
        element={
          <ProtectedRoute allowedRoles={['project_manager']}>
            <JoinRequestsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId/control"
        element={
          <ProtectedRoute>
            <ProjectControlPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId/dashboard"
        element={
          <ProtectedRoute>
            <ProjectDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId/floors/:floorId"
        element={
          <ProtectedRoute>
            <FloorDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId/qc/floors/:floorId/run/:runId/stage/:stageId"
        element={
          <ProtectedRoute>
            <StageDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId/qc"
        element={
          <ProtectedRoute>
            <QCFloorSelectionPage />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route
        path="/projects/:projectId/plans"
        element={
          <ProtectedRoute>
            <ProjectPlansPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId/tasks"
        element={
          <ProtectedRoute>
            <ProjectTasksPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId/units/:unitId"
        element={
          <ProtectedRoute>
            <UnitHomePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId/units/:unitId/tasks"
        element={
          <ProtectedRoute>
            <UnitDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId/units/:unitId/plans"
        element={
          <ProtectedRoute>
            <UnitPlansPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/tasks/:id"
        element={
          <ProtectedRoute>
            <TaskDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
          path="/org/transfer/settings"
          element={
            <ProtectedRoute>
              <OwnershipTransferPage />
            </ProtectedRoute>
          }
        />
        <Route path="/org/transfer/:token" element={<OwnershipTransferPage />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
};

function App() {
  return (
    <AuthProvider>
      <BillingProvider>
        <IdentityProvider>
          <BrowserRouter>
            <div className="App">
              <PaywallConnector />
              <TrialBanner />
              <CompleteAccountBanner />
              <AppRoutes />
              <PaywallModal />
              <CompleteAccountModal />
              <Toaster position="top-center" dir="rtl" />
            </div>
          </BrowserRouter>
        </IdentityProvider>
      </BillingProvider>
    </AuthProvider>
  );
}

export default App;
