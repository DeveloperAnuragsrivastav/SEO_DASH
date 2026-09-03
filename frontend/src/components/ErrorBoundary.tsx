import { Component } from 'react';

import type { ErrorInfo, ReactNode } from 'react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '48px', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: 'var(--bg-app)' }}>
          <div className="card" style={{ maxWidth: '500px', width: '100%', textAlign: 'center' }}>
            <div className="card-header" style={{ borderBottom: 'none', paddingBottom: 0 }}>
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>💥</div>
              <h1 className="h1">Something went wrong</h1>
            </div>
            <div className="card-body">
              <p className="text-subtle" style={{ marginBottom: '24px' }}>
                An unexpected error occurred in the application. Please try reloading the page.
              </p>
              {this.state.error && (
                <div style={{ background: 'var(--bg-surface-hover)', padding: '12px', borderRadius: '4px', fontSize: '12px', color: 'var(--status-error)', fontFamily: 'monospace', textAlign: 'left', marginBottom: '24px', overflowX: 'auto' }}>
                  {this.state.error.toString()}
                </div>
              )}
              <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                <button className="btn btn-secondary" onClick={() => window.location.href = '/'}>
                  Go Home
                </button>
                <button className="btn btn-primary" onClick={() => window.location.reload()}>
                  Reload Page
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
