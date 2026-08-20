import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../../api/client';
import LoadingSpinner from '../../components/LoadingSpinner';
import { Plug, Settings, Bot } from 'lucide-react';
import { AdminShell } from '../../components/layout/AdminShell';
import { btnPrimary } from '../../components/kit';

interface Client {
  id: string;
  name: string;
  domain: string;
  business_type: string;
  status: string;
  package_keywords: number;
  locale: string;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="font-serif text-3xl leading-none text-white">{value}</span>
      <span className="mt-1 block font-mono text-[10px] uppercase tracking-[0.08em] text-white/40">
        {label}
      </span>
    </div>
  );
}

export default function ClientDashboard() {
  const { clientId } = useParams<{ clientId: string }>();
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [connectionCount, setConnectionCount] = useState(0);
  const [keywordCount, setKeywordCount] = useState(0);
  const [promptCount, setPromptCount] = useState(0);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [clientRes, connRes, kwRes, promptRes] = await Promise.allSettled([
          api.get(`/clients/${clientId}`),
          api.get(`/clients/${clientId}/connections`),
          api.get(`/clients/${clientId}/keywords`),
          api.get(`/clients/${clientId}/ai_prompts`),
        ]);
        if (clientRes.status === 'fulfilled') setClient(clientRes.value.data);
        if (connRes.status === 'fulfilled') setConnectionCount(connRes.value.data?.length || 0);
        if (kwRes.status === 'fulfilled') setKeywordCount(kwRes.value.data?.length || 0);
        if (promptRes.status === 'fulfilled') setPromptCount(promptRes.value.data?.length || 0);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    if (clientId) fetchAll();
  }, [clientId]);

  if (loading) return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading client…" /></div></AdminShell>;
  if (!client) return <div className="p-8 text-red-500">Client not found</div>;

  const currentMonth = new Date().toISOString().slice(0, 7);
  const formattedMonth = new Date(currentMonth + '-01').toLocaleString('default', { month: 'long', year: 'numeric' });

  const cards = [
    {
      icon: <Plug className="size-5 text-brand" />,
      title: "Connections",
      body: connectionCount > 0
        ? `${connectionCount} data source${connectionCount !== 1 ? 's' : ''} connected for ${client.name}.`
        : `No data sources connected yet for ${client.name}.`,
      action: "Manage Connections",
      to: `/admin/clients/${client.id}/connections`,
    },
    {
      icon: <Settings className="size-5 text-brand" />,
      title: "Keywords",
      body: keywordCount > 0
        ? `${keywordCount} of ${client.package_keywords} package keywords actively tracked.`
        : `${client.package_keywords} keyword slots available. None tracked yet.`,
      action: "Manage Keywords",
      to: `/clients/${client.id}/keywords`,
    },
    {
      icon: <Bot className="size-5 text-brand" />,
      title: "AI Prompts",
      body: promptCount > 0
        ? `${promptCount} prompt${promptCount !== 1 ? 's' : ''} configured for AI visibility monitoring.`
        : `No AI prompts configured yet for ${client.name}.`,
      action: "Manage Prompts",
      to: `/clients/${client.id}/ai-prompts`,
    },
  ];

  return (
    <AdminShell
      breadcrumb={client.name}
      title={client.name}
      subtitle={`${client.domain} • ${client.business_type}`}
      actions={
        <Link
          to={`/clients/${client.id}/reports/${currentMonth}/overview`}
          className={btnPrimary}
        >
          View Current Report →
        </Link>
      }
    >
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {cards.map((card) => (
          <section
            key={card.title}
            className="flex flex-col rounded-lg border border-border bg-card p-6 transition-shadow hover:shadow-[0_4px_12px_rgba(0,0,0,0.06)]"
          >
            <span className="flex size-10 items-center justify-center rounded-md bg-brand-soft">
              {card.icon}
            </span>
            <h2 className="mt-4 font-serif text-2xl leading-none">{card.title}</h2>
            <p className="mt-3 flex-1 text-sm text-muted-foreground">{card.body}</p>
            <Link
              to={card.to}
              className="mt-6 block rounded-md border border-border py-2 text-center text-sm font-medium transition-colors hover:bg-secondary"
            >
              {card.action}
            </Link>
          </section>
        ))}
      </div>
    </AdminShell>
  );
}
