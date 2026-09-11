import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import { ErrorBoundary } from './components/ErrorBoundary';
import { RootRedirect } from './components/RootRedirect';
import { Toaster } from 'sonner';

import Login from './pages/Login';
import Clients from './pages/admin/Clients';
import ClientDashboard from './pages/admin/ClientDashboard';
import Connections from './pages/admin/Connections';
import ManualEntryHub from './pages/admin/ManualEntryHub';
import Keywords from './pages/admin/Keywords';
import AIPrompts from './pages/admin/AIPrompts';
import Screenshots from './pages/admin/Screenshots';
import AIMentionsData from './pages/admin/AIMentionsData';
import GBPManagement from './pages/admin/GBPManagement';
import LinksManagement from './pages/admin/LinksManagement';
import WorkManagement from './pages/admin/WorkManagement';
import GoogleAnalytics from './pages/admin/GoogleAnalytics';
import SearchConsole from './pages/admin/SearchConsole';
import Users from './pages/admin/Users';
import ManagerDashboard from './pages/admin/ManagerDashboard';
import ReportView from './pages/ReportView';
import ReportBuilder from './pages/ReportBuilder';

import { AdminLayout } from './components/layout/AdminLayout';

const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <Toaster position="top-right" richColors />
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />

            <Route element={<ProtectedRoute />}>
              {/* Admin pages with header nav */}
              <Route element={<AdminLayout />}>
                <Route path="/" element={<RootRedirect />} />
                <Route path="/admin/clients" element={<Clients />} />
                <Route path="/admin/clients/:clientId" element={<ClientDashboard />} />
                <Route path="/admin/clients/:clientId/connections" element={<Connections />} />
                <Route path="/admin/clients/:clientId/manual-entry" element={<ManualEntryHub />} />
                <Route path="/clients/:clientId/keywords" element={<Keywords />} />
                <Route path="/clients/:clientId/ai-prompts" element={<AIPrompts />} />
                <Route path="/clients/:clientId/screenshots" element={<Screenshots />} />
                <Route path="/clients/:clientId/ai-mentions-data" element={<AIMentionsData />} />
                <Route path="/clients/:clientId/manual-metrics" element={<ManualEntryHub />} />
                <Route path="/clients/:clientId/gbp" element={<GBPManagement />} />
                <Route path="/clients/:clientId/google-analytics" element={<GoogleAnalytics />} />
                <Route path="/clients/:clientId/search-console" element={<SearchConsole />} />
                <Route path="/clients/:clientId/links" element={<LinksManagement />} />
                <Route path="/clients/:clientId/work" element={<WorkManagement />} />
                <Route element={<ProtectedRoute allowedRoles={['super_admin']} />}>
                  <Route path="/admin/users" element={<Users />} />
                </Route>
                <Route element={<ProtectedRoute allowedRoles={['manager']} />}>
                  <Route path="/admin/manager-tools" element={<ManagerDashboard />} />
                </Route>

                {/* Reports stay inside the app shell — leaving it to read a
                    report made it feel like a different product. */}
                {/* The builder comes before the report: it asks what to include,
                    fills in connected sources and takes manual figures for the rest. */}
                <Route path="/clients/:clientId/reports/:snapshotId/build" element={<ReportBuilder />} />
                <Route path="/admin/clients/:clientId/reports/:snapshotId/build" element={<ReportBuilder />} />
                <Route path="/clients/:clientId/reports/:snapshotId" element={<ReportView />} />
                <Route path="/admin/clients/:clientId/reports/:snapshotId" element={<ReportView />} />
              </Route>
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
};

export default App;
