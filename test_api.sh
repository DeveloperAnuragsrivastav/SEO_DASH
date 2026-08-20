#!/bin/bash
BASE_URL="http://localhost:8000"

TOKEN=$(curl -s -X POST "$BASE_URL/auth/token" -d "username=admin@ezrankings.com&password=password123" | grep -o '"access_token":"[^"]*' | grep -o '[^"]*$')

echo "Token: $TOKEN"

echo -e "\n1. Create Client"
CLIENT_RES=$(curl -s -X POST "$BASE_URL/clients" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name":"Acme Test Corp","domain":"acme.example.com","business_type":"saas","locale":"en-US","package_keywords":20,"status":"active"}')
echo "$CLIENT_RES"
CLIENT_ID=$(echo "$CLIENT_RES" | grep -o '"id":"[^"]*' | grep -o '[^"]*$')
echo "Client ID: $CLIENT_ID"

echo -e "\n2. Add Connection"
CONN_RES=$(curl -s -X POST "$BASE_URL/clients/$CLIENT_ID/connections" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"provider":"gsc","property_id":"sc-domain:acme.example.com"}')
echo "$CONN_RES"
CONN_ID=$(echo "$CONN_RES" | grep -o '"id":"[^"]*' | grep -o '[^"]*$')
echo "Conn ID: $CONN_ID"

echo -e "\n3. Verify Connection"
curl -s -X POST "$BASE_URL/connections/$CONN_ID/verify" -H "Authorization: Bearer $TOKEN"
echo ""
