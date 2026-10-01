import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Image as ImageIcon, ExternalLink } from 'lucide-react';
import api from '../../api/client';
import Page, { Empty, LoadError } from '../../components/ui/Page';
import PageSkeleton from '../../components/ui/PageSkeleton';
import '../../sheets.css';

type Shot = { section: string; slot: number; caption: string };
type MonthShots = { month: string; label: string; report: string; images: Shot[] };

const SECTION_NAME: Record<string, string> = { gbp: 'Business Profile', ai: 'AI answers', ai_summary: 'AI results (source)' };

/** One screenshot, fetched with the session's token (an <img> can't send it). */
function Thumb({ clientId, report, shot, onOpen }: { clientId: string; report: string; shot: Shot; onOpen: (src: string) => void }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    api.get(`/clients/${clientId}/reports/${report}/images/${shot.section}/${shot.slot}`, { responseType: 'blob', skipErrorToast: true } as any)
      .then(res => { url = URL.createObjectURL(res.data); setSrc(url); })
      .catch(() => {});
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [clientId, report, shot.section, shot.slot]);
  return (
    <figure className="shots-item" onClick={() => src && onOpen(src)}>
      <div className="frame">{src ? <img src={src} alt={shot.caption || 'Screenshot'} /> : <ImageIcon size={18} />}</div>
      <figcaption><span className="shots-tag">{SECTION_NAME[shot.section] || shot.section}</span>{shot.caption ? ` · ${shot.caption}` : ''}</figcaption>
    </figure>
  );
}

/** Every published report's screenshots, month by month — a record, not an inbox. */
const Screenshots: React.FC = () => {
  const { clientId } = useParams();
  const [months, setMonths] = useState<MonthShots[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const [failed, setFailed] = useState(false);
  const load = () => {
    setFailed(false);
    api.get(`/clients/${clientId}/sheets/screenshots/months`)
      .then(res => setMonths(res.data || []))
      .catch(() => { setFailed(true); setMonths([]); });
  };
  useEffect(load, [clientId]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(null); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  if (months === null) return <PageSkeleton />;
  const withShots = months.filter(m => m.images.length);

  return (
    <Page screen="screenshots">
      <section className="surface">
        {failed ? (
          <LoadError what="the screenshots" onRetry={() => { setMonths(null); load(); }} />
        ) : withShots.length === 0 ? (
          <Empty
            icon={<ImageIcon size={22} />}
            title="No published screenshots yet"
            hint="Screenshots added in the report builder appear here, under their month, once the report is published."
          />
        ) : withShots.map(m => (
          <div key={m.month} className="shots-month">
            <div className="shots-month-head">
              <h3>{m.label}</h3>
              <span className="sh-meta">{m.images.length} screenshot{m.images.length === 1 ? '' : 's'}</span>
              <Link className="sh-report" to={`/admin/clients/${clientId}/reports/${m.report}`} title="Open the report"><ExternalLink size={12} /></Link>
            </div>
            <div className="shots-grid">
              {m.images.map(s => <Thumb key={`${s.section}-${s.slot}`} clientId={clientId!} report={m.report} shot={s} onOpen={setOpen} />)}
            </div>
          </div>
        ))}
      </section>
      {open && <div className="shots-light" onClick={() => setOpen(null)}><img src={open} alt="" /></div>}
    </Page>
  );
};

export default Screenshots;
