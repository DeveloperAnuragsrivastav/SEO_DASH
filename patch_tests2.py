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

patch_file('SearchPerformance.test.tsx', [
    ("if (url === '/clients/client123/search/2026-08')",
     "if (url === '/clients/client123') return Promise.resolve({ data: { name: 'Test Client' } });\n      if (url === '/clients/client123/search/2026-08')")
])

patch_file('Audience.test.tsx', [
    ("if (url === '/clients/client123/audience/2026-08')",
     "if (url === '/clients/client123') return Promise.resolve({ data: { name: 'Test Client' } });\n      if (url === '/clients/client123/audience/2026-08')")
])

patch_file('KeywordsAdmin.test.tsx', [
    ("vi.mocked(api.get).mockResolvedValueOnce({\n      data: []",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({\n      data: []"),
    ("vi.mocked(api.get).mockResolvedValueOnce({\n      data: mockKeywords",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({\n      data: mockKeywords")
])

patch_file('AIPromptsAdmin.test.tsx', [
    ("vi.mocked(api.get).mockResolvedValueOnce({\n      data: []",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({\n      data: []"),
    ("vi.mocked(api.get).mockResolvedValueOnce({\n      data: mockPrompts",
     "vi.mocked(api.get).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({\n      data: mockPrompts")
])

