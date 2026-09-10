import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/client';
import { ArrowRight, Building2, ExternalLink } from 'lucide-react';

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

const statusClass = (status: string) =>
  status === 'active' ? 'badge-success' : status === 'paused' ? 'badge-warning' : 'badge-neutral';

const Clients: React.FC = () => {
  const { isManager } = usePermissions();
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchClients = async () => {
    try {
      const res = await api.get('/clients');
      setClients(res.data || []);
    } catch (err) {
      // Handled by global interceptor
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

      {clients.length === 0 ? (
        <div className="page-card">
          <div className="empty-state">
            <span className="empty-state-icon"><Building2 size={22} /></span>
            <h3>No projects yet</h3>
            <p>Once a project is assigned to you it will appear here with its keywords, traffic and reporting history.</p>
          </div>
        </div>
      ) : (
        <div className="client-grid">
          {clients.map(c => (
            <Link key={c.id} to={`/admin/clients/${c.id}`} className="client-card">
              <div className="client-card-top">
                <span className="client-monogram">{c.name.slice(0, 2)}</span>
                <span className={`badge ${statusClass(c.status)}`}>{c.status.toUpperCase()}</span>
              </div>

              <h3 className="client-name">{c.name}</h3>

              <span
                className="client-domain"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); window.open(`https://${c.domain}`, '_blank', 'noopener,noreferrer'); }}
                role="link"
                tabIndex={-1}
              >
                {c.domain} <ExternalLink size={11} />
              </span>

              <div className="client-meta">
                <div>
                  <div className="overline">Keywords</div>
                  <div className="client-meta-value mono">{c.package_keywords}</div>
                </div>
                <div>
                  <div className="overline">Type</div>
                  <div className="client-meta-value" style={{ textTransform: 'capitalize' }}>{c.business_type}</div>
                </div>
              </div>

              <span className="client-cta">
                View Dashboard <ArrowRight size={14} />
              </span>
            </Link>
          ))}
        </div>
      )}
    </>
  );
};

export default Clients;
