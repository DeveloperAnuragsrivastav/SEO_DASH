from __future__ import annotations
import requests
import json

base_url = "http://localhost:8000"

res = requests.post(f"{base_url}/auth/login", data={"username": "admin@ezrankings.com", "password": "password123"})
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("=== 1. Create Client ===")
c_res = requests.post(f"{base_url}/clients", json={"name": "API Test Client", "domain": "api.com", "business_type": "saas", "locale": "en-US", "package_keywords": 20, "status": "active"}, headers=headers)
print("Status Code:", c_res.status_code)
print("Response Body:\n", json.dumps(c_res.json(), indent=2))
client_id = c_res.json()["id"]

print("\n=== 2. Add Connection ===")
conn_res = requests.post(f"{base_url}/clients/{client_id}/connections", json={"provider": "gsc", "property_id": "sc-domain:api.com"}, headers=headers)
print("Status Code:", conn_res.status_code)
print("Response Body:\n", json.dumps(conn_res.json(), indent=2))
conn_id = conn_res.json()["id"]

print("\n=== 3. Verify Connection ===")
verify_res = requests.post(f"{base_url}/connections/{conn_id}/verify", headers=headers)
print("Status Code:", verify_res.status_code)
print("Response Body:\n", json.dumps(verify_res.json(), indent=2))

