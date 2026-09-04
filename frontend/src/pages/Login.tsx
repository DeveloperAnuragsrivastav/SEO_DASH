import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import api from '../api/client';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
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
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      login(res.data.access_token);
      navigate('/');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Login failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Left: Branded Panel */}
      <div className="login-brand">
        <div className="login-brand-content" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <img src="/logo6.png" alt="EZ Insights" loading="eager" fetchPriority="high" style={{ width: '100%', maxWidth: '360px', height: 'auto', marginBottom: '32px' }} />
          <p>SEO intelligence, reporting & performance analytics</p>
        </div>
      </div>

      {/* Right: Login Form */}
      <div className="login-form-side">
        <div className="login-form-card">
          <h1>Welcome back</h1>
          <p className="text-subtle">Sign in to your agency portal</p>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Email address</label>
              <input className="form-input" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@agency.com" autoFocus />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input className="form-input" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <div style={{ marginTop: 24 }}>
              <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Login;
