import { useAuth } from '../context/AuthContext';

export const usePermissions = () => {
  const { user } = useAuth();

  const isSuperAdmin = user?.role === 'super_admin';
  const isManager = user?.role === 'manager';
  const isStandardUser = user?.role === 'user';

  return {
    isSuperAdmin,
    isManager,
    isStandardUser,
    
    // Check if the current user can view the global admin tools (like the managers list)
    canViewAdminTools: isSuperAdmin,
    
    // Check if the current user can view manager tools (like user creation, assigning projects)
    canViewManagerTools: isManager,
    
    // Check if user has at least manager privileges
    isAtLeastManager: isSuperAdmin || isManager,
  };
};
