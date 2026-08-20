from __future__ import annotations
import re

with open('ez-rankings-login.html', 'r') as f:
    html = f.read()

style_match = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
if style_match:
    print("--- STYLE ---")
    print(style_match.group(1))

body_match = re.search(r'<body>(.*?)</body>', html, re.DOTALL)
if body_match:
    body_content = body_match.group(1)
    body_content = re.sub(r'src="data:image/png;base64,[^"]+"', 'src="dashboard-illustration.png"', body_content)
    print("--- BODY ---")
    print(body_content)
