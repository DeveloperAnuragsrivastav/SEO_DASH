import re

with open('frontend/src/components/report/TrafficSection.tsx', 'r') as f:
    content = f.read()

# Fix the extra </div>
content = content.replace("          </div>\n          </div>\n        </div>", "          </div>\n        </div>")

# For the topPages, ga4Sources, ga4Pages, ga4Devices, I broke the JSX tags.
# Let me just restore from the version I have if I have a backup.
# Wait, let's just write a regex to clean it up.
