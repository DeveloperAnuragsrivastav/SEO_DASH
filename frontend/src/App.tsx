import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Users from './pages/admin/Users';
import Keywords from './pages/admin/Keywords';
import AIPrompts from './pages/admin/AIPrompts';

import Login from './pages/Login';
import Overview from './pages/Overview';
import Rankings from './pages/Rankings';
import SearchPerformance from './pages/SearchPerformance';
import Audience from './pages/Audience';
import AIVisibility from './pages/AIVisibility';
import Links from './pages/Links';
import WorkDone from './pages/WorkDone';
import Clients from './pages/admin/Clients';
import Connections from './pages/admin/Connections';
import ClientDashboard from './pages/admin/ClientDashboard';
import { AppLayout } from './components/layout/AppLayout';

const DashboardHome = () => <Navigate to="/admin/clients" replace />;

const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<DashboardHome />} />
              <Route path="/admin/clients" element={<Clients />} />
              <Route path="/admin/clients/:clientId" element={<ClientDashboard />} />
              <Route path="/admin/clients/:clientId/connections" element={<Connections />} />
              <Route path="/clients/:clientId/reports/:month/overview" element={<Overview />} />
              <Route path="/clients/:clientId/reports/:month/rankings" element={<Rankings />} />
              <Route path="/clients/:clientId/reports/:month/search" element={<SearchPerformance />} />
              <Route path="/clients/:clientId/reports/:month/audience" element={<Audience />} />
              <Route path="/clients/:clientId/reports/:month/ai-visibility" element={<AIVisibility />} />
              <Route path="/clients/:clientId/reports/:month/links" element={<Links />} />
              <Route path="/clients/:clientId/reports/:month/work" element={<WorkDone />} />
              <Route element={<ProtectedRoute allowedRoles={['agency_admin']} />}>
                <Route path="/admin/users" element={<Users />} />
              </Route>
              
              <Route path="/clients/:clientId/keywords" element={<Keywords />} />
              <Route path="/clients/:clientId/ai-prompts" element={<AIPrompts />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
