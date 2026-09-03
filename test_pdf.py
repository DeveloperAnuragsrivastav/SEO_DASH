import urllib.request
import urllib.parse
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 1. Login to get token
data = urllib.parse.urlencode({"username": "admin@ezrankings.com", "password": "password"}).encode("utf-8")
req = urllib.request.Request("http://localhost:8000/auth/login", data=data)
try:
    with urllib.request.urlopen(req, context=ctx) as res:
        token = json.loads(res.read())["access_token"]
except Exception as e:
    print(f"Login failed: {e}")
    exit(1)

# 2. Download PDF
req = urllib.request.Request(
    "http://localhost:8000/clients/6d64979f-abb8-45e4-a9f5-4ab1fac4508f/reports/2026-08/pdf",
    headers={"Authorization": f"Bearer {token}"}
)
try:
    with urllib.request.urlopen(req, context=ctx) as res:
        pdf_data = res.read()
        print(f'Status: {res.status}, Type: {res.headers.get("Content-Type")}, Size: {len(pdf_data)} bytes')
        with open('test.pdf', 'wb') as f:
            f.write(pdf_data)
        print("PDF saved as test.pdf")
except Exception as e:
    print(f"PDF download failed: {e}")
