import React, { useEffect, Suspense } from 'react';
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
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';
import './index.css';

import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import RegisterManagementPage from './pages/RegisterManagementPage';
import OnboardingPage from './pages/OnboardingPage';
import PendingApprovalPage from './pages/PendingApprovalPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import AccessibilityPage from './pages/AccessibilityPage';
import WaLoginPage from './pages/WaLoginPage';

const JoinRequestsPage = React.lazy(() => import('./pages/JoinRequestsPage'));
const TaskDetailPage = React.lazy(() => import('./pages/TaskDetailPage'));
const AdminPage = React.lazy(() => import('./pages/AdminPage'));
const AdminBillingPage = React.lazy(() => import('./pages/AdminBillingPage'));
const OrgBillingPage = React.lazy(() => import('./pages/OrgBillingPage'));
const AdminUsersPage = React.lazy(() => import('./pages/AdminUsersPage'));
const AdminOrgsPage = React.lazy(() => import('./pages/AdminOrgsPage'));
const ProjectControlPage = React.lazy(() => import('./pages/ProjectControlPage'));
const UnitDetailPage = React.lazy(() => import('./pages/UnitDetailPage'));
const UnitHomePage = React.lazy(() => import('./pages/UnitHomePage'));
const UnitPlansPage = React.lazy(() => import('./pages/UnitPlansPage'));
const ProjectTasksPage = React.lazy(() => import('./pages/ProjectTasksPage'));
const ProjectPlansPage = React.lazy(() => import('./pages/ProjectPlansPage'));
const ProjectPlansArchivePage = React.lazy(() => import('./pages/ProjectPlansArchivePage'));
const ProjectPlanHistoryPage = React.lazy(() => import('./pages/ProjectPlanHistoryPage'));
const MyProjectsPage = React.lazy(() => import('./pages/MyProjectsPage'));
const ContractorDashboard = React.lazy(() => import('./pages/ContractorDashboard'));
const OwnershipTransferPage = React.lazy(() => import('./pages/OwnershipTransferPage'));
const ProjectDashboardPage = React.lazy(() => import('./pages/ProjectDashboardPage'));
const FloorDetailPage = React.lazy(() => import('./pages/FloorDetailPage'));
const StageDetailPage = React.lazy(() => import('./pages/StageDetailPage'));
const QCFloorSelectionPage = React.lazy(() => import('./pages/QCFloorSelectionPage'));
const AccountSettingsPage = React.lazy(() => import('./pages/AccountSettingsPage'));
const BuildingDefectsPage = React.lazy(() => import('./pages/BuildingDefectsPage'));
const BuildingQCPage = React.lazy(() => import('./pages/BuildingQCPage'));
const UnitQCSelectionPage = React.lazy(() => import('./pages/UnitQCSelectionPage'));
const InnerBuildingPage = React.lazy(() => import('./pages/InnerBuildingPage'));
const AdminQCTemplatesPage = React.lazy(() => import('./pages/AdminQCTemplatesPage'));
const ApartmentDashboardPage = React.lazy(() => import('./pages/ApartmentDashboardPage'));
const HandoverOverviewPage = React.lazy(() => import('./pages/HandoverOverviewPage'));
const HandoverTabPage = React.lazy(() => import('./pages/HandoverTabPage'));
const HandoverProtocolPage = React.lazy(() => import('./pages/HandoverProtocolPage'));
const HandoverSectionPage = React.lazy(() => import('./pages/HandoverSectionPage'));

const INTENDED_PATH_KEY = 'intendedPath';

const LoadingSpinner = () => (
  <div className="min-h-screen flex items-center justify-center bg-slate-50">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-500"></div>
  </div>
);

const ProtectedRoute = ({ children, allowedRoles, requireSuperAdmin }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (!user) {
    const currentPath = location.pathname + location.search + location.hash;
    if (currentPath && currentPath !== '/' && currentPath !== '/login' && currentPath !== '/projects') {
      sessionStorage.setItem(INTENDED_PATH_KEY, currentPath);
      sessionStorage.setItem('deepLinkSource', 'external');
      console.log('[DEEP_LINK] ProtectedRoute: saved target', currentPath);
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

const ProjectsHome = () => {
  const { user } = useAuth();
  if (user?.role === 'contractor') return <ContractorDashboard />;
  return <MyProjectsPage />;
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
  const location = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Routes key={location.pathname}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/phone-login" element={<Navigate to="/login" replace />} />
        <Route path="/auth/wa" element={<WaLoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/register-management" element={<RegisterManagementPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/accessibility" element={<AccessibilityPage />} />
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
              <ProjectsHome />
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
          path="/admin/orgs"
          element={
            <ProtectedRoute requireSuperAdmin>
              <AdminOrgsPage />
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
          path="/admin/qc-templates"
          element={
            <ProtectedRoute requireSuperAdmin>
              <AdminQCTemplatesPage />
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
          path="/projects/:projectId/buildings/:buildingId/floors/:floorId/qc/units"
          element={
            <ProtectedRoute>
              <UnitQCSelectionPage />
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
          path="/projects/:projectId/plans/archive"
          element={
            <ProtectedRoute>
              <ProjectPlansArchivePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/plans/:planId/history"
          element={
            <ProtectedRoute>
              <ProjectPlanHistoryPage />
            </ProtectedRoute>
          }
        />
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
          path="/projects/:projectId/handover"
          element={
            <ProtectedRoute>
              <HandoverOverviewPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/units/:unitId/handover"
          element={
            <ProtectedRoute>
              <HandoverTabPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/units/:unitId/handover/:protocolId"
          element={
            <ProtectedRoute>
              <HandoverProtocolPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/units/:unitId/handover/:protocolId/sections/:sectionId"
          element={
            <ProtectedRoute>
              <HandoverSectionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/buildings/:buildingId"
          element={
            <ProtectedRoute>
              <InnerBuildingPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/buildings/:buildingId/qc"
          element={
            <ProtectedRoute>
              <BuildingQCPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/buildings/:buildingId/defects"
          element={
            <ProtectedRoute>
              <BuildingDefectsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:projectId/units/:unitId/defects"
          element={
            <ProtectedRoute>
              <ApartmentDashboardPage />
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
    </Suspense>
  );
};

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BillingProvider>
          <IdentityProvider>
            <BrowserRouter>
              <div className="App">
                <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:right-2 focus:z-[9999] focus:bg-amber-500 focus:text-white focus:px-4 focus:py-2 focus:rounded-lg focus:text-sm focus:font-medium">
                  דלג לתוכן הראשי
                </a>
                <PaywallConnector />
                <TrialBanner />
                <CompleteAccountBanner />
                <main id="main-content" tabIndex={-1} style={{ outline: 'none' }}>
                  <AppRoutes />
                </main>
                <PaywallModal />
                <CompleteAccountModal />
                <Toaster position="top-center" dir="rtl" />
              </div>
            </BrowserRouter>
          </IdentityProvider>
        </BillingProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
