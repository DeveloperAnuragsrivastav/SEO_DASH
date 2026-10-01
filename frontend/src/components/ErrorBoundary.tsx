import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
  children?: ReactNode;
  /** "page" keeps the sidebar and header working; "app" covers the screen. */
  variant?: 'page' | 'app';
  /** Changing this (e.g. the URL) clears the error, so moving on recovers. */
  resetKey?: string;
}

interface State {
  error: Error | null;
}

/** Catches a crash while drawing a screen and offers a way out, instead of a blank page. */
export class ErrorBoundary extends Component<Props, State> {
  public state: State = { error: null };

  public static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  public componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Screen crashed:', error, info.componentStack);
  }

  public componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  public render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const page = this.props.variant === 'page';
    return (
      <div className={`crash ${page ? 'crash-page' : 'crash-app'}`} role="alert">
        <div className="crash-card">
          <span className="crash-icon"><AlertTriangle size={20} /></span>
          <h1 className="crash-title">This screen couldn’t be shown</h1>
          <p className="crash-text">
            Something unexpected went wrong while loading it. Nothing you saved is lost — try again,
            or go back to the client list.
          </p>
          <details className="crash-details">
            <summary>Technical details</summary>
            <code>{error.message || String(error)}</code>
          </details>
          <div className="crash-actions">
            <button className="btn btn-secondary" onClick={() => { window.location.href = '/admin/clients'; }}>Go to clients</button>
            <button className="btn btn-primary" onClick={() => (page ? this.setState({ error: null }) : window.location.reload())}>Try again</button>
          </div>
        </div>
      </div>
    );
  }
}
