import re

with open('frontend/src/pages/admin/ManualEntryHub.tsx', 'r') as f:
    content = f.read()

screenshots_form = """
const ScreenshotsManualForm = ({ clientId, onComplete }: { clientId: string, onComplete: () => void }) => {
  const [month, setMonth] = useState('');
  const [caption, setCaption] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      toast.error('Please select an image file');
      return;
    }
    
    setUploading(true);
    const formData = new FormData();
    formData.append('month', month);
    formData.append('caption', caption);
    formData.append('file', file);
    
    try {
      await api.post(`/clients/${clientId}/screenshots`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Screenshot uploaded successfully');
      onComplete();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to upload screenshot');
    }
    setUploading(false);
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
      <div className="form-group"><label className="form-label">Report Month</label><input type="date" className="form-input" required value={month} onChange={e => setMonth(e.target.value)} /></div>
      <div className="form-group"><label className="form-label">Caption (Optional)</label><input type="text" className="form-input" placeholder="e.g. GSC Traffic Peak" value={caption} onChange={e => setCaption(e.target.value)} /></div>
      <div className="form-group">
        <label className="form-label">Image File</label>
        <input type="file" className="form-input" accept="image/*" required onChange={e => setFile(e.target.files ? e.target.files[0] : null)} />
      </div>
      <button type="submit" className="btn btn-primary" style={{marginTop: '8px', width: '100%'}} disabled={uploading}>
        {uploading ? 'Uploading...' : 'Upload Screenshot'}
      </button>
    </form>
  );
};

// --- Main Components ---
"""

content = content.replace('// --- Main Components ---', screenshots_form)

screenshot_card = """
        <IngestionCard 
          title="Screenshots"
          manualForm={<ScreenshotsManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />
      </div>
"""

content = content.replace('</div>\n    </>\n  );\n};\n\nexport default ManualEntryHub;', screenshot_card + '    </>\n  );\n};\n\nexport default ManualEntryHub;')

with open('frontend/src/pages/admin/ManualEntryHub.tsx', 'w') as f:
    f.write(content)
