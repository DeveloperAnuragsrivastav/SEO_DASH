from __future__ import annotations
import re
import base64

with open('ez-rankings-login.html', 'r') as f:
    html = f.read()

match = re.search(r'src="data:image/png;base64,([^"]+)"', html)
if match:
    img_data = base64.b64decode(match.group(1))
    with open('frontend/public/dashboard-illustration.png', 'wb') as img_file:
        img_file.write(img_data)
    print("Image extracted.")
else:
    print("No image found.")
