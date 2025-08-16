#!/bin/bash
# Deployment Health Check Script
# Tests all health endpoints for deployment systems

echo "🔍 Testing deployment health endpoints..."
echo "============================================"

# Test root endpoint with empty user agent (load balancer simulation)
echo "1. Testing root endpoint (/) with empty user agent:"
response=$(curl -s -w "%{http_code}" -H "User-Agent:" http://localhost:5000/)
echo "Response: $response"

# Test root endpoint with GoogleHC user agent
echo -e "\n2. Testing root endpoint (/) with GoogleHC user agent:"
response=$(curl -s -w "%{http_code}" -H "User-Agent: GoogleHC/1.0" http://localhost:5000/)
echo "Response: $response"

# Test root endpoint with HEAD method
echo -e "\n3. Testing root endpoint (/) with HEAD method:"
response=$(curl -I -s -w "%{http_code}" http://localhost:5000/)
echo "Response: $response"

# Test dedicated health endpoints
echo -e "\n4. Testing /health endpoint:"
response=$(curl -s -w "%{http_code}" http://localhost:5000/health)
echo "Response: $response"

echo -e "\n5. Testing /healthz endpoint:"
response=$(curl -s -w "%{http_code}" http://localhost:5000/healthz)
echo "Response: $response"

echo -e "\n6. Testing /ready endpoint:"
response=$(curl -s -w "%{http_code}" http://localhost:5000/ready)
echo "Response: $response"

echo -e "\n7. Testing /live endpoint:"
response=$(curl -s -w "%{http_code}" http://localhost:5000/live)
echo "Response: $response"

echo -e "\n8. Testing API health endpoint:"
response=$(curl -s -w "%{http_code}" http://localhost:5000/api/health)
echo "Response: $response"

echo -e "\n9. Testing API healthz endpoint:"
response=$(curl -s -w "%{http_code}" http://localhost:5000/api/healthz)
echo "Response: $response"

echo -e "\n✅ Health check testing complete!"
echo "All endpoints should return 200 status codes for successful deployment."