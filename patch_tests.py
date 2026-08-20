from __future__ import annotations
import os
import re

TEST_DIR = 'frontend/src/__tests__'

def patch_file(filename, replacements):
    filepath = os.path.join(TEST_DIR, filename)
    if not os.path.exists(filepath):
        print(f"Skipping {filename}, not found.")
        return
    
    with open(filepath, 'r') as f:
        content = f.read()
        
    original = content
    for old, new in replacements:
        content = content.replace(old, new)
        
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Patched {filename}")
    else:
        print(f"No changes made to {filename}")

patch_file('AIVisibility.test.tsx', [
    ("(api.get as any).mockImplementation(() => new Promise(() => {}));", 
     "(api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockImplementation(() => new Promise(() => {}));"),
    ("(api.get as any).mockResolvedValueOnce({ data: mockData });",
     "(api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: mockData });")
])

patch_file('Links.test.tsx', [
    ("(api.get as any).mockImplementation(() => new Promise(() => {}));",
     "(api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockImplementation(() => new Promise(() => {}));"),
    ("(api.get as any).mockResolvedValueOnce({ data: mockData });",
     "(api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: mockData });")
])

patch_file('WorkDone.test.tsx', [
    ("(api.get as any).mockImplementation(() => new Promise(() => {}));",
     "(api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockImplementation(() => new Promise(() => {}));"),
    ("(api.get as any).mockResolvedValueOnce({ data: mockData });",
     "(api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: mockData });")
])

patch_file('SearchPerformance.test.tsx', [
    ("vi.mocked(api.get).mockResolvedValueOnce({ data: mockData });",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: mockData });")
])

patch_file('Audience.test.tsx', [
    ("vi.mocked(api.get).mockResolvedValueOnce({ data: mockData });",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: mockData });")
])

patch_file('KeywordsAdmin.test.tsx', [
    ("vi.mocked(api.get).mockResolvedValueOnce({ data: [] });",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: [] });"),
    ("vi.mocked(api.get).mockResolvedValue({",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({")
])

patch_file('AIPromptsAdmin.test.tsx', [
    ("vi.mocked(api.get).mockResolvedValueOnce({ data: [] });",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: [] });"),
    ("vi.mocked(api.get).mockResolvedValue({",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({")
])

patch_file('ConnectionsAdmin.test.tsx', [
    ("vi.mocked(api.get).mockResolvedValueOnce({ data: [] });",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: [] });"),
    ("vi.mocked(api.get).mockResolvedValue({",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({")
])

patch_file('Overview.test.tsx', [
    ("if (url === '/clients/client123/reports/2026-08') return Promise.reject({ response: { status: 404 } });",
     "if (url === '/clients/client123') return Promise.resolve({ data: { name: 'Test Client' } });\n      if (url === '/clients/client123/reports/2026-08') return Promise.reject({ response: { status: 404 } });"),
    ("if (url === '/clients/client123/reports/2026-08') return Promise.resolve({ data: mockData });",
     "if (url === '/clients/client123') return Promise.resolve({ data: { name: 'Test Client' } });\n      if (url === '/clients/client123/reports/2026-08') return Promise.resolve({ data: mockData });")
])
