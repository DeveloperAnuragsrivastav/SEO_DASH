import axios from 'axios';
import { toast } from 'sonner';

export const API_BASE_URL = import.meta.env.VITE_API_URL !== undefined 
  ? import.meta.env.VITE_API_URL 
  : 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to attach the JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Global error interceptor — shows real backend errors to the user
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle 401 — trigger global logout
    if (error.response?.status === 401) {
      window.dispatchEvent(new Event('auth:unauthorized'));
      return Promise.reject(error);
    }

    // Extract the real error message from the backend
    const status = error.response?.status;
    const data = error.response?.data;

    let message = 'Something went wrong. Please try again.';

    if (data) {
      if (typeof data.detail === 'string') {
        // FastAPI standard: { "detail": "Error message here" }
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        // FastAPI validation errors: { "detail": [{ "msg": "...", "loc": [...] }] }
        message = data.detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join(', ');
      } else if (typeof data.message === 'string') {
        message = data.message;
      } else if (typeof data.error === 'string') {
        message = data.error;
      }
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      message = 'Request timed out. Please check your connection and try again.';
    } else if (!error.response) {
      message = 'Network error. Unable to reach the server.';
    }

    // Add status code context for non-obvious errors
    const prefix = status === 403 ? '⛔ Access Denied: '
                 : status === 404 ? '🔍 Not Found: '
                 : status === 422 ? '⚠️ Validation Error: '
                 : status === 500 ? '🔥 Server Error: '
                 : status === 502 ? '🔧 Service Unavailable: '
                 : status === 503 ? '🔧 Service Unavailable: '
                 : '';

    // Show the toast — but let individual page catch blocks override if they want
    // We use a slight delay so page-level toasts can suppress this if needed
    if (!(error as any)._toastHandled) {
      toast.error(prefix + message, {
        duration: 5000,
      });
    }

    return Promise.reject(error);
  }
);

export default api;
