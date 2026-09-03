import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';

export function AdminLayout() {
  return (
    <div className="app-layout">
      <Sidebar />
      
      <div className="app-main">
        <header className="app-header">
          <div className="h2" style={{ color: 'var(--text-secondary)' }}>Dashboard</div>
          {/* We can add a global search or top-level actions here in the future */}
        </header>
        
        <main className="app-content">
          <div className="content-max-width">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
