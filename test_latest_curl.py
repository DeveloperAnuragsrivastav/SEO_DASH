import requests

login_data = {
    "username": "admin@example.com",
    "password": "password"
}
# Try standard admin login
r = requests.post("http://localhost:8000/auth/login", data=login_data)
if r.status_code != 200:
    # Try another password or endpoint if needed. But usually dev systems have admin/password or similar
    print("Login failed:", r.text)
else:
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    r2 = requests.get("http://localhost:8000/clients/f3e327e6-909e-4922-8bbc-552ac6edb9c0/reports/latest", headers=headers)
    print("Status:", r2.status_code)
    print("Body:", r2.text)

