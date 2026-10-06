import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams, Link } from 'react-router-dom';
import api from '../api/client';
import { Loader2, CloudDownload, Database, Layers } from 'lucide-react';
import type { PeriodsInfo } from '../components/PeriodPicker';
import { periodLabel } from '../components/PeriodPicker';
import '../builder.css';

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

/**
 * Generating a report: starts it, says honestly what is happening, and opens
 * the builder as soon as the draft exists.
 */
const ReportPreparing: React.FC = () => {
  const { clientId } = useParams<{ clientId: string }>();
  const [params] = useSearchParams();
  const months = Math.max(1, Number(params.get('months')) || 1);
  // A client's first report: the period picked on the client page.
  const pickedStart = params.get('start') || undefined;
  const pickedEnd = params.get('end') || undefined;
  const navigate = useNavigate();

  const [info, setInfo] = useState<PeriodsInfo | null>(null);
  const [error, setError] = useState<{ text: string; draftId?: string | null } | null>(null);

  // Development renders effects twice; the report must still start only once.
  const started = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  useEffect(() => {
    if (started.current || !clientId) return;
    started.current = true;

    (async () => {
      let before: string | null = null;
      try {
        const [periods, latest] = await Promise.all([
          api.get(`/clients/${clientId}/reports/periods`),
          api.get(`/clients/${clientId}/reports/latest`, { skipErrorToast: true } as any).catch(() => ({ data: null })),
        ]);
        setInfo(periods.data);
        before = latest.data?.id ?? null;
        if (periods.data.mode === 'draft') {
          setError({ text: 'This period already has a draft report.', draftId: periods.data.report_id });
          return;
        }
      } catch (e) {
        // Handled by global interceptor
      }

      try {
        await api.post(`/clients/${clientId}/reports/generate`, { months, start: pickedStart, end: pickedEnd }, { skipErrorToast: true } as any);
      } catch (e: any) {
        setError({ text: e?.response?.data?.detail || 'The report could not be started.' });
        return;
      }

      for (let i = 0; i < 60; i++) {
        await sleep(i === 0 ? 1500 : 3000);
        if (!alive.current) return;
        // The server says how the build is going: a failure shows at once,
        // with its reason, instead of after a three-minute wait.
        try {
          const st = await api.get(`/clients/${clientId}/reports/generate/status`, { skipErrorToast: true } as any);
          if (st.data?.state === 'failed') {
            setError({ text: st.data.error || 'The report could not be built.' });
            return;
          }
          if (st.data?.state === 'done' && st.data.report_id) {
            navigate(`/admin/clients/${clientId}/reports/${st.data.report_id}/build`, { replace: true });
            return;
          }
        } catch (e) {
          // The status is a shortcut; the report itself is checked below.
        }
        try {
          const r = await api.get(`/clients/${clientId}/reports/latest`, { skipErrorToast: true } as any);
          if (r.data?.id && r.data.id !== before) {
            navigate(`/admin/clients/${clientId}/reports/${r.data.id}/build`, { replace: true });
            return;
          }
        } catch (e) {
          // Not there yet
        }
      }
      if (alive.current) setError({ text: 'This is taking longer than usual (over 3 minutes) — Google may be slow to answer. The report will appear under All reports when it is ready; come back in a few minutes.' });
    })();
  }, [clientId]);

  const cycles = info?.cycles || [];
  const chosen = cycles.slice(Math.max(0, cycles.length - months));
  const d = (s: string) => new Date(`${s}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const picked = pickedStart && pickedEnd ? { label: `${d(pickedStart)} – ${d(pickedEnd)}` } : null;
  const current = picked || chosen[chosen.length - 1];
  const earlier = chosen.slice(0, -1);
  const google = [info?.connected?.gsc && 'Search Console', info?.connected?.ga4 && 'Analytics'].filter(Boolean).join(' and ');

  return (
    <div className="prep">
      <h1>Preparing the report</h1>
      <p className="prep-sub">
        {picked ? `${picked.label} · first report` : <>{cycles.length ? periodLabel(cycles, Math.min(months, cycles.length)) : 'This period'} · {months} month{months === 1 ? '' : 's'}</>}.
        The builder opens as soon as the figures are ready — you can check and change everything there.
      </p>

      <ul className="prep-steps">
        <li>
          {google ? <CloudDownload size={17} /> : <Database size={17} />}
          <span>
            {google ? `Fetching ${current?.label || 'this period'} from ${google}` : `${current?.label || 'This period'}: no Google connection`}
            <small>{google ? 'Only the current period (and the one before, to compare) is pulled from Google.' : "You'll add this period's figures with a sheet in the builder."}</small>
          </span>
        </li>
        {!picked && earlier.length > 0 && (
          <li>
            <Database size={17} />
            <span>
              Reading {earlier.length === 1 ? earlier[0].label : `${earlier[0].label} – ${earlier[earlier.length - 1].label}`} from saved data
              <small>Nothing old is pulled again.</small>
            </span>
          </li>
        )}
        {months > 1 && (
          <li>
            <Layers size={17} />
            <span>Combining {months} months into one report<small>Clicks and sessions add up; rates and positions are recalculated, not averaged.</small></span>
          </li>
        )}
      </ul>

      {error ? (
        <div className="notice notice-warning prep-error">
          <p className="notice-body">{error.text}</p>
          <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            {error.draftId && (
              <Link className="btn btn-primary btn-sm" to={`/admin/clients/${clientId}/reports/${error.draftId}/build`}>Open the draft</Link>
            )}
            <Link className="btn btn-secondary btn-sm" to={`/admin/clients/${clientId}`}>Back to client</Link>
          </div>
        </div>
      ) : (
        <p className="prep-foot"><Loader2 size={13} className="spin" style={{ verticalAlign: '-2px', marginRight: 6 }} />Usually under a minute.</p>
      )}
    </div>
  );
};

export default ReportPreparing;
