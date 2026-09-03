import React, { useState } from 'react';
import { ClipboardList, X } from 'lucide-react';
import { API_BASE_URL } from '../../api/client';

interface WorkDoneSectionProps {
  activities: any[];
  screenshots: any[];
  months?: string[];
}

const WorkDoneSection: React.FC<WorkDoneSectionProps> = ({ activities, screenshots }) => {
  const [selectedImg, setSelectedImg] = useState<string | null>(null);

  return (
    <section id="work" className="report-section">
      <div className="head">
        <div>
          <div className="eyebrow">Project Delivery</div>
          <h2>Work Done & Proof</h2>
        </div>
        <span className="spacer" />
        <span className="src man">Manual entry</span>
      </div>
      
      {activities.length === 0 && screenshots.length === 0 ? (
        <div className="card pad" style={{ textAlign: 'center', marginTop: 'var(--space-md)', padding: '48px 16px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
            <ClipboardList size={32} color="var(--ink-3)" />
          </div>
          <p className="text-subtle" style={{ margin: 0 }}>No work activities or screenshots recorded for this month.</p>
        </div>
      ) : (
        <>
          {activities.length > 0 && (
            <div className="card pad" style={{ marginTop: 'var(--space-md)' }}>
              <h3 className="h2" style={{ fontSize: '16px', marginBottom: '16px' }}>Delivered Work</h3>
              <div className="grid grid-cols-2">
                {activities.map((a: any, i: number) => (
                  <div key={i} className="bar-row" style={{ gridTemplateColumns: '1fr auto auto', padding: '12px 16px', background: 'var(--neutral-bg)', borderRadius: 'var(--radius-sm)' }}>
                    <div className="lab" style={{ color: 'var(--ink)' }}>✓ {a.activity_type}</div>
                    <div className="num" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)' }}>{a.count}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {screenshots.length > 0 && (
            <div className="card pad" style={{ marginTop: 'var(--space-lg)' }}>
              <h3 className="h2" style={{ fontSize: '16px', marginBottom: '4px' }}>Proof & Screenshots</h3>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                Visual evidence of search placements, AI answers, and completed work.
              </div>
              <div className="shots-grid">
                {screenshots.map((s: any, i: number) => (
                  <div key={i} className="shot-card">
                    <div className="thumb">
                      {s.file_url && (
                        <img 
                          src={`${API_BASE_URL}${s.file_url}`} 
                          alt={s.caption || `Screenshot ${i + 1}`} 
                          loading="lazy" 
                          onClick={() => setSelectedImg(`${API_BASE_URL}${s.file_url}`)}
                          style={{ cursor: 'zoom-in', transition: 'transform 0.2s' }}
                          onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.02)'}
                          onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
                        />
                      )}
                    </div>
                    <div className="label text-subtle">{s.caption || `Screenshot ${i + 1}`} <span style={{fontSize:'10px'}}>({s._month})</span></div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Fullscreen Image Modal */}
      {selectedImg && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.85)',
            zIndex: 99999,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: '40px',
            cursor: 'zoom-out'
          }}
          onClick={() => setSelectedImg(null)}
        >
          <button 
            style={{ position: 'absolute', top: '20px', right: '20px', background: 'none', border: 'none', color: 'white', cursor: 'pointer' }}
            onClick={() => setSelectedImg(null)}
          >
            <X size={32} />
          </button>
          <img 
            src={selectedImg} 
            alt="Enlarged" 
            style={{ 
              maxWidth: '100%', 
              maxHeight: '100%', 
              objectFit: 'contain', 
              borderRadius: '8px',
              boxShadow: '0 20px 40px rgba(0,0,0,0.4)'
            }} 
          />
        </div>
      )}
    </section>
  );
};

export default WorkDoneSection;
