import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import api from '../api/client';
import { Eye, EyeOff, BarChart3, FileText, Sparkles, Loader2 } from 'lucide-react';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) { toast.error('Enter email and password.'); return; }
    setLoading(true);
    try {
      const form = new URLSearchParams();
      form.append('username', email);
      form.append('password', password);

      const res = await api.post('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        skipErrorToast: true,
      } as any);
      login(res.data.access_token);
      navigate('/');
    } catch (err: any) {
      const status = err.response?.status;
      toast.error(
        status === 401 ? 'Wrong email or password'
          : !err.response ? 'Can’t reach the server'
          : 'Sign-in failed',
        { id: 'login-error', description: status === 401 ? 'Check both and try again.' : (err.response?.data?.detail || 'Please try again in a moment.') },
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Left: Branded Panel */}
      <div className="login-brand">
        <div className="login-brand-content">
          <img src="/logo6.png" alt="EZ Insights" loading="eager" fetchPriority="high" className="login-brand-logo" />
        </div>

        <div className="login-brand-content">
          <h2>Every SEO signal your clients care about, in one report.</h2>
          <p>Rankings, traffic, backlinks and AI visibility — consolidated, verified and ready to present.</p>

          <div className="login-points">
            <div className="login-point"><BarChart3 size={16} /> Live Search Console &amp; Analytics sync</div>
            <div className="login-point"><Sparkles size={16} /> AI prompt visibility tracking</div>
            <div className="login-point"><FileText size={16} /> One-click white-labelled PDF reports</div>
          </div>
        </div>
      </div>

      {/* Right: Login Form */}
      <div className="login-form-side">
        <div className="login-form-card">
          <h1>Welcome back</h1>
          <p className="text-subtle">Sign in to your agency portal</p>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label" htmlFor="login-email">Email address</label>
              <input
                id="login-email"
                className="form-input"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@agency.com"
                autoComplete="username"
                autoFocus
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="login-password">Password</label>
              <div className="input-affix">
                <input
                  id="login-password"
                  className="form-input"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="input-affix-btn"
                  onClick={() => setShowPassword(v => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button type="submit" className="btn btn-primary btn-lg btn-block" style={{ marginTop: 8 }} disabled={loading}>
              {loading ? <><Loader2 size={16} className="spin" /> Signing in…</> : 'Sign in'}
            </button>
          </form>

          <div className="login-foot">Protected area · Authorised agency staff only</div>
        </div>
      </div>
    </div>
  );
};

export default Login;
