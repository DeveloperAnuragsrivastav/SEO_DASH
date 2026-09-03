import glob, os

for file in glob.glob("app/models/*.py"):
    with open(file, 'r') as f:
        lines = f.readlines()
    
    # Remove any misplaced Optional imports and duplicate future imports
    new_lines = []
    seen_future = False
    for line in lines:
        if 'from typing import Optional' in line:
            continue
        if 'from __future__ import annotations' in line:
            if seen_future:
                continue
            seen_future = True
        new_lines.append(line)
        
    # Insert typing.Optional after future import
    for i, line in enumerate(new_lines):
        if 'from __future__ import annotations' in line:
            new_lines.insert(i+1, "from typing import Optional\n")
            break
    else:
        new_lines.insert(0, "from typing import Optional\n")
            
    with open(file, 'w') as f:
        f.writelines(new_lines)
