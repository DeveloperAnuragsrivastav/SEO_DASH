from __future__ import annotations
import requests

base_url = "http://localhost:8000"

res = requests.post(f"{base_url}/auth/login", data={"username": "admin@ezrankings.com", "password": "password123"})
if res.status_code != 200:
    print("Login failed!", res.text)
    exit(1)
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

c_res = requests.post(f"{base_url}/clients", json={"name": "API Test Client", "domain": "api.com", "business_type": "saas", "locale": "en-US", "package_keywords": 20, "status": "active"}, headers=headers)
print("Client:", c_res.status_code, c_res.json())
client_id = c_res.json()["id"]

conn_res = requests.post(f"{base_url}/clients/{client_id}/connections", json={"provider": "gsc", "property_id": "sc-domain:api.com"}, headers=headers)
print("Connection:", conn_res.status_code, conn_res.json())
conn_id = conn_res.json()["id"]

verify_res = requests.post(f"{base_url}/connections/{conn_id}/verify", headers=headers)
print("Verify:", verify_res.status_code, verify_res.text)

