import React, { useEffect, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { BillingProvider, useBilling } from './contexts/BillingContext';
import { IdentityProvider } from './contexts/IdentityContext';
import { setPaywallCallback } from './services/api';
import { setLanguage } from './i18n';
import { Toaster } from './components/ui/sonner';
import TrialBanner from './components/TrialBanner';
import CompleteAccountBanner from './components/CompleteAccountBanner';
import CompleteAccountModal from './components/CompleteAccountModal';
import PaywallModal from './components/PaywallModal';
import ErrorBoundary from './components/ErrorBoundary';
import { StatusBar, Style } from '@capacitor/status-bar';
import { Capacitor } from '@capacitor/core';
import { App as CapacitorApp } from '@capacitor/app';
import { CapacitorUpdater } from '@capgo/capacitor-updater';
import BrikSplash from './components/splash/BrikSplash';
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
import PendingDeletionPage from './pages/PendingDeletionPage';
import PaymentSuccessPage from './pages/PaymentSuccessPage';
import PaymentFailurePage from './pages/PaymentFailurePage';

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
const AdminDashboardPage = React.lazy(() => import('./pages/AdminDashboardPage'));
const AdminActivityPage = React.lazy(() => import('./pages/AdminActivityPage'));
const AdminQCTemplatesPage = React.lazy(() => import('./pages/AdminQCTemplatesPage'));
const AdminHandoverTemplateEditor = React.lazy(() => import('./pages/AdminHandoverTemplateEditor'));
const ApartmentDashboardPage = React.lazy(() => import('./pages/ApartmentDashboardPage'));
const HandoverOverviewPage = React.lazy(() => import('./pages/HandoverOverviewPage'));
const HandoverTabPage = React.lazy(() => import('./pages/HandoverTabPage'));
const HandoverProtocolPage = React.lazy(() => import('./pages/HandoverProtocolPage'));
const HandoverSectionPage = React.lazy(() => import('./pages/HandoverSectionPage'));
const SafetyHomePage = React.lazy(() => import('./pages/SafetyHomePage'));

const INTENDED_PATH_KEY = 'intendedPath';

// Wave 2b: BrikSplash now owns its own lifecycle and is mounted once at
// the App shell (see <AppShell/> below). The placeholder here is a tiny
// non-splash gradient used ONLY for the rare network-error case inside
// ProtectedRoute. z-index 9998 keeps it under BrikSplash (9999) and well
// below Sonner toasts so error messages stay visible on top.
const NetworkPlaceholder = ({ label }) => (
  <div style={{
    position: 'fixed', inset: 0, zIndex: 9998,
    background: 'linear-gradient(180deg,#3A4258 0%,#323A4E 50%,#2A3142 100%)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#B8C5DB', fontFamily: 'Rubik, system-ui', fontSize: 14,
    direction: 'rtl',
  }} role="status" aria-live="polite">{label}</div>
);

const ProtectedRoute = ({ children, allowedRoles, requireSuperAdmin }) => {
  const { user, loading, token, networkError } = useAuth();
  const location = useLocation();

  const userRole = user?.role;
  const userLang = user?.preferred_language;
  useEffect(() => {
    if (userRole === 'contractor' && userLang) {
      setLanguage(userLang);
    } else if (userRole && userRole !== 'contractor') {
      setLanguage('he');
    }
  }, [userLang, userRole]);

  if (loading) {
    // Defensive: BrikSplash already gates on isAppReady so this branch
    // should normally be unreachable on cold boot. Kept for safety in
    // case ProtectedRoute remounts mid-session while auth refreshes.
    return <NetworkPlaceholder label="טוען" />;
  }

  if (!user && token && networkError) {
    return <NetworkPlaceholder label="מתחבר…" />;
  }

  if (!user) {
    const currentPath = location.pathname + location.search + location.hash;
    if (currentPath && currentPath !== '/' && currentPath !== '/login' && currentPath !== '/projects') {
      sessionStorage.setItem(INTENDED_PATH_KEY, currentPath);
      sessionStorage.setItem('deepLinkSource', 'external');
    }
    return <Navigate to="/login" replace />;
  }

  if (user.user_status === 'pending_pm_approval' || user.user_status === 'pending') {
    return <Navigate to="/pending" replace />;
  }

  if (user.user_status === 'pending_deletion') {
    return <Navigate to="/account/pending-deletion" replace />;
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
    <Suspense fallback={null}>
      <Routes key={location.pathname}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/phone-login" element={<Navigate to="/login" replace />} />
        <Route path="/auth/wa" element={<WaLoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/register-management" element={<RegisterManagementPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/accessibility" element={<AccessibilityPage />} />
        <Route path="/billing/payment-success" element={<PaymentSuccessPage />} />
        <Route path="/billing/payment-failure" element={<PaymentFailurePage />} />
        <Route path="/billing/payment-cancel" element={<PaymentFailurePage />} />
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
        <Route path="/account/pending-deletion" element={<PendingDeletionPage />} />
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
          path="/admin/dashboard"
          element={
            <ProtectedRoute requireSuperAdmin>
              <AdminDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/activity"
          element={
            <ProtectedRoute requireSuperAdmin>
              <AdminActivityPage />
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
          path="/admin/templates/handover/:templateId/edit"
          element={
            <ProtectedRoute requireSuperAdmin>
              <AdminHandoverTemplateEditor />
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
        <Route
          path="/projects/:projectId/safety"
          element={
            <ProtectedRoute allowedRoles={['project_manager', 'management_team', 'owner', 'admin']}>
              <SafetyHomePage />
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

// Wave 2b: BrikSplash is mounted ONCE here, wrapping the routed app
// tree. It owns its own minimum display time (3600ms D3-A, 800ms D2)
// and reveals children only when both the timer fires AND auth resolves.
const AppShell = () => {
  const { loading } = useAuth();
  return (
    <BrikSplash isAppReady={!loading}>
      <AppRoutes />
    </BrikSplash>
  );
};

function App() {
  useEffect(() => {
    if (Capacitor.isNativePlatform()) {
      StatusBar.setOverlaysWebView({ overlay: false });
      StatusBar.setBackgroundColor({ color: '#0F172A' });
      StatusBar.setStyle({ style: Style.Dark });
      try {
        CapacitorUpdater.notifyAppReady();
      } catch (e) {
        console.warn('Capgo notifyAppReady failed:', e);
      }
    }
  }, []);

  useEffect(() => {
    if (!Capacitor.isNativePlatform?.()) return;

    const listenerPromise = CapacitorApp.addListener('backButton', ({ canGoBack }) => {
      if (canGoBack) {
        window.history.back();
      } else {
        CapacitorApp.exitApp();
      }
    });

    return () => {
      listenerPromise.then(listener => listener.remove()).catch(() => {});
    };
  }, []);

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
                  <AppShell />
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
// capgo smoke test Sat Apr 18 02:36:05 PM UTC 2026
// capgo run #3 test Sat Apr 18 02:42:01 PM UTC 2026
// capgo run #3 test Sat Apr 18 03:12:54 PM UTC 2026
