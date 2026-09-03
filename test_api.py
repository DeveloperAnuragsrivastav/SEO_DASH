import requests

url = "http://localhost:8000/api/clients/f3e327e6-909e-4922-8bbc-552ac6edb9c0/reports/latest"
response = requests.get(url, headers={'Authorization': 'Bearer test'})
print(response.status_code)
print(response.text[:1000])
