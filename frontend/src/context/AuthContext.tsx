import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import api from '../api/client';

export interface User {
  id: string;
  email: string;
  role: string;
}

interface AuthContextType {
  token: string | null;
  user: User | null;
  login: (token: string) => void;
  logout: () => void;
  isLoading: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

// DECISION: Using localStorage for JWT persistence. 
// WHY: The token has a 24-hour lifespan with no refresh token mechanism. 
// If stored purely in memory (React state), the user would be forced to re-login on every page refresh,
// resulting in very poor UX. Because this is an internal-only admin tool with no arbitrary 
// user-generated content (like forums or comments), the XSS risk profile is much lower than a 
// public-facing application, making localStorage an acceptable trade-off for usability.

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const login = (newToken: string) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  useEffect(() => {
    // Listen for the global unauthorized event emitted by the API client
    const handleUnauthorized = () => logout();
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  useEffect(() => {
    const fetchUser = async () => {
      if (!token) {
        setIsLoading(false);
        return;
      }
      
      try {
        const response = await api.get('/auth/me');
        setUser(response.data);
      } catch (error) {
        // If it's a 401, the interceptor will trigger the 'auth:unauthorized' event and logout
        // Otherwise, we might have a network error. We won't log out immediately on network errors.
      } finally {
        setIsLoading(false);
      }
    };

    fetchUser();
  }, [token]);

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
