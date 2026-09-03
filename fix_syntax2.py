import glob, os, re

for file in glob.glob("app/models/*.py"):
    with open(file, 'r') as f:
        content = f.read()
    
    if 'Optional[Mapped[' in content:
        # replace Optional[Mapped[Type]] with Mapped[Optional[Type]]
        content = re.sub(r'Optional\[Mapped\[([^\]]+)\]\]', r'Mapped[Optional[\1]]', content)
        
        with open(file, 'w') as f:
            f.write(content)
        print(f"Fixed {file}")
