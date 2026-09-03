import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/client';
import { toast } from 'sonner';
import { usePermissions } from '../../hooks/usePermissions';
import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';

interface ClientRow {
  id: string;
  name: string;
  domain: string;
  status: string;
  package_keywords: number;
  business_type: string;
}

const Clients: React.FC = () => {
  const { isManager } = usePermissions();
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchClients = async () => {
    try {
      const res = await api.get('/clients');
      setClients(res.data || []);
    } catch { 
      toast.error('Failed to load clients.'); 
    } finally { 
      setLoading(false); 
    }
  };

  useEffect(() => { fetchClients(); }, []);


  const active = clients.filter(c => c.status === 'active').length;
  const totalKw = clients.reduce((s, c) => s + (c.package_keywords || 0), 0);

  if (loading) return <PageSkeleton cards={6} header={true} stats={0} />;

  return (
    <>
      <PageHeader 
        title={isManager ? "My Clients" : "Assigned Projects"}
        subtitle={`${active} active · ${totalKw} keywords tracked`}
        breadcrumbs={[{ label: 'Home', href: '/' }, { label: 'Clients' }]}
        actions={undefined}
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
        {clients.length === 0 ? (
          <div className="page-card" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '64px' }}>
            <p className="text-subtle">No projects found.</p>
          </div>
        ) : (
          clients.map(c => (
            <div key={c.id} className="page-card" style={{ display: 'flex', flexDirection: 'column', padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                <div>
                  <h3 className="h2" style={{ marginBottom: '4px', fontSize: '18px' }}>{c.name}</h3>
                  <a href={`https://${c.domain}`} target="_blank" rel="noreferrer" className="text-subtle text-sm" style={{ textDecoration: 'none' }}>
                    {c.domain}
                  </a>
                </div>
                <span className={`badge ${c.status === 'active' ? 'badge-success' : c.status === 'paused' ? 'badge-warning' : 'badge-neutral'}`}>
                  {c.status.toUpperCase()}
                </span>
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px', paddingBottom: '20px', borderBottom: '1px solid var(--border-subtle)' }}>
                <div>
                  <div className="text-subtle text-xs" style={{ textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px', fontWeight: 600 }}>Keywords</div>
                  <div className="mono" style={{ fontSize: '15px' }}>{c.package_keywords}</div>
                </div>
                <div>
                  <div className="text-subtle text-xs" style={{ textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px', fontWeight: 600 }}>Type</div>
                  <div style={{ fontSize: '14px', textTransform: 'capitalize' }}>{c.business_type}</div>
                </div>
              </div>
              
              <Link to={`/admin/clients/${c.id}`} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>
                View Dashboard →
              </Link>
            </div>
          ))
        )}
      </div>


    </>
  );
};

export default Clients;
