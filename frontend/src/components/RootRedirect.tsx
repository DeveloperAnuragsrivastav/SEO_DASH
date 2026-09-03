import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function RootRedirect() {
  const { user } = useAuth();
  
  if (!user) {
    return <div className="loader"><div className="loader-ring" /></div>;
  }
  
  if (user.role === 'super_admin') {
    return <Navigate to="/admin/users" replace />;
  }
  
  if (user.role === 'manager') {
    return <Navigate to="/admin/manager-tools" replace />;
  }
  
  return <Navigate to="/admin/clients" replace />;
}
