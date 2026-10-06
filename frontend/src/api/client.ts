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

/** The backend's own words for a failure, when it sent any. */
async function readDetail(data: unknown): Promise<string | null> {
  // Downloads (PDFs, images) ask for a Blob, so an error body arrives as one too.
  if (typeof Blob !== 'undefined' && data instanceof Blob) {
    try { data = JSON.parse(await data.text()); } catch { return null; }
  }
  if (!data || typeof data !== 'object') return null;
  const d = data as any;
  if (typeof d.detail === 'string') return d.detail;
  if (Array.isArray(d.detail)) {
    // FastAPI validation: name the field, not just "Field required".
    return d.detail.map((e: any) => {
      const field = Array.isArray(e.loc) ? e.loc.filter((x: unknown) => x !== 'body' && x !== 'query').join(' › ') : '';
      const msg = String(e.msg || e.message || 'is not valid').replace(/^Value error, /, '');
      return field ? `${field}: ${msg}` : msg;
    }).join('\n');
  }
  if (typeof d.message === 'string') return d.message;
  if (typeof d.error === 'string') return d.error;
  return null;
}

/** A plain heading for each kind of failure; the detail goes underneath. */
function headingFor(status: number | undefined, offline: boolean, timedOut: boolean): string {
  if (timedOut) return 'That took too long';
  if (offline) return 'Can’t reach the server';
  switch (status) {
    case 400: return 'That didn’t work';
    case 403: return 'You don’t have access to this';
    case 404: return 'Not found';
    case 409: return 'Can’t do that right now';
    case 413: return 'That file is too large';
    case 422: return 'Please check what you entered';
    case 429: return 'Too many requests';
    default: return status && status >= 500 ? 'Something went wrong on our side' : 'Something went wrong';
  }
}

// Global error handling: every failed request shows one toast in the app's
// own style, unless the caller opted out with `{ skipErrorToast: true }`.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status: number | undefined = error.response?.status;

    // Signed out (expired or revoked token): say so once, then log out.
    const isLogin = String(error.config?.url || '').includes('/auth/login');
    if (status === 401 && !isLogin) {
      if (localStorage.getItem('token')) {
        toast.error('Your session has ended', { id: 'session-ended', description: 'Please sign in again.' });
      }
      window.dispatchEvent(new Event('auth:unauthorized'));
      return Promise.reject(error);
    }

    if (axios.isCancel(error) || (error.config as any)?.skipErrorToast === true) {
      return Promise.reject(error);
    }

    const timedOut = error.code === 'ECONNABORTED' || /timeout/i.test(error.message || '');
    const offline = !error.response && !timedOut;
    const detail = error.response ? await readDetail(error.response.data) : null;
    const heading = headingFor(status, offline, timedOut);
    const description = detail
      || (offline ? 'Check your internet connection and try again.'
        : timedOut ? 'The server is busy. Please try again in a moment.'
        : status && status >= 500 ? 'Please try again in a moment. If it keeps happening, tell your admin.'
        : undefined);

    // Same failure twice (a retry, a double click) updates one toast instead of stacking.
    toast.error(heading, { id: `${heading}|${description || ''}`, description, duration: 6000 });

    // Callers read the message the same way they always have.
    if (detail && error.response) (error as any).userMessage = detail;
    return Promise.reject(error);
  }
);

/** One readable sentence for a failed request: the server's own reason when
 *  it gave one, otherwise what the status means. For screens that show the
 *  error in place (the toast already appeared). */
export function errorText(e: any, what = 'this'): string {
  if (e?.userMessage) return e.userMessage;
  const d = e?.response?.data?.detail;
  if (typeof d === 'string' && d) return d;
  const status: number | undefined = e?.response?.status;
  if (!e?.response) return 'Can’t reach the server — check your internet connection, then try again.';
  if (status === 403) return `You don’t have access to ${what}.`;
  if (status === 404) return `${what[0].toUpperCase()}${what.slice(1)} no longer exists — it may have been deleted.`;
  if (status && status >= 500) return `The server hit a problem with ${what}. Try again — if it keeps happening, tell your admin.`;
  return `${what[0].toUpperCase()}${what.slice(1)} could not be loaded (error ${status}).`;
}

export default api;
