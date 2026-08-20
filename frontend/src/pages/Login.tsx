import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import './Login.css'; // Import the new CSS

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim() || !password.trim()) {
      setError('Enter your email and password.');
      return;
    }

    setIsSubmitting(true);

    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await axios.post(
        `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/auth/login`,
        formData,
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        }
      );

      login(response.data.access_token);
      navigate('/admin/clients');
    } catch (err: any) {
      if (err.response?.status === 401) {
        setError('Incorrect email or password');
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-container">
      <div className="story">
        <div className="brand">
          <div className="badge">EZ</div>
          <div className="name">EZ Rankings</div>
        </div>

        <div className="illustration-wrap">
          <img src="public/bg.png" alt="Five people manually tracking SEO data, one person calmly using EZ Rankings instead" />
        </div>

        <div className="story-copy">
          <h1>Five different jobs.<br />Now <span>one calm dashboard.</span></h1>
          <p>Rankings, traffic, search console, backlinks, listings — no more jumping between tabs and people. EZ Rankings brings every signal into one screen.</p>
        </div>
      </div>

      <div className="form-panel">
        <div className="form-inner">
          <h2>Welcome back</h2>
          <p className="sub">Sign in to your agency dashboard.</p>

          {error && (
            <div style={{ marginBottom: '20px', padding: '12px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '10px', color: '#ef4444', fontSize: '13.5px' }}>
              {error}
            </div>
          )}

          {/* <button className="google-btn" type="button">
            <svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"/><path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.97v2.33A9 9 0 0 0 9 18z"/><path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.97A9 9 0 0 0 0 9c0 1.45.35 2.83.97 4.05l3-2.33z"/><path fill="#EA4335" d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.59-2.59C13.46.9 11.43 0 9 0A9 9 0 0 0 .97 4.95l3 2.33C4.68 5.16 6.66 3.58 9 3.58z"/></svg>
            Sign in with Google
          </button>

          <div className="divider">or sign in with email</div> */}

          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="email">Email address</label>
              <input id="email" type="email" placeholder="you@agency.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>

            <div className="field">
              <label htmlFor="password">Password</label>
              <input id="password" type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>

            <div className="row-between">
              <span></span>
              {/* <a href="#">Forgot password?</a> */}
            </div>

            <button type="submit" className="signin-btn" disabled={isSubmitting}>
              {isSubmitting ? "Signing in..." : "Sign In"}
            </button>
          </form>

          {/* <p className="footnote">Don't have an account? <a href="#">Contact your admin</a></p> */}
        </div>
      </div>
    </div>
  );
};

export default Login;
