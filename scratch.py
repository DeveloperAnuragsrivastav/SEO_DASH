import os
import re

directories = ['app', 'tests']

for directory in directories:
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r') as f:
                    content = f.read()
                
                # Remove from __future__ import annotations
                new_content = re.sub(r'from __future__ import annotations\n', '', content)
                
                # Replace Optional[X] with X | None
                # First, find any Optional[X] where X is a single word
                new_content = re.sub(r'Optional\[([a-zA-Z0-9_]+)\]', r'\1 | None', new_content)
                # Also replace Optional[list[dict]] etc., a simple non-greedy match inside Optional[]
                new_content = re.sub(r'Optional\[([^\]]+)\]', r'\1 | None', new_content)
                
                # We should also remove 'from typing import Optional' if it's unused, but it's fine to leave it.
                # Let's remove it if it exists by itself
                new_content = re.sub(r'from typing import Optional\n', '', new_content)
                
                if content != new_content:
                    with open(filepath, 'w') as f:
                        f.write(new_content)
                    print(f"Updated {filepath}")
