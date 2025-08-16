#!/usr/bin/env python3
"""
Ultra-simple health check test to verify deployment readiness
"""
import requests
import sys
import time

def test_health_endpoint(url, user_agent=None, method='GET'):
    """Test a health endpoint with specific user agent"""
    try:
        headers = {}
        if user_agent:
            headers['User-Agent'] = user_agent
        
        start_time = time.time()
        if method == 'HEAD':
            response = requests.head(url, headers=headers, timeout=10)
        else:
            response = requests.get(url, headers=headers, timeout=10)
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        print(f"✅ {method} {url}")
        print(f"   User-Agent: {user_agent or 'None'}")
        print(f"   Status: {response.status_code}")
        print(f"   Response Time: {response_time:.1f}ms")
        print(f"   Content: {response.text[:50]}...")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ {method} {url}")
        print(f"   User-Agent: {user_agent or 'None'}")
        print(f"   Error: {e}")
        return False

def main():
    base_url = 'http://localhost:5000'
    
    print("🔍 DEPLOYMENT HEALTH CHECK VERIFICATION")
    print("=" * 50)
    
    # Test scenarios that deployment systems use
    test_cases = [
        ('/', None, 'GET'),  # Empty user agent
        ('/', '', 'GET'),    # Explicit empty user agent  
        ('/', 'GoogleHC/1.0', 'GET'),  # Google Cloud health checks
        ('/', 'curl/7.68.0', 'GET'),   # curl requests
        ('/', 'Health Check', 'GET'),   # Generic health check
        ('/', 'probe', 'GET'),          # Probe agents
        ('/', None, 'HEAD'),            # HEAD requests
        ('/health', None, 'GET'),       # Dedicated health endpoint
        ('/healthz', None, 'GET'),      # Alternative health endpoint
        ('/api/health', None, 'GET'),   # API health endpoint
    ]
    
    results = []
    for endpoint, user_agent, method in test_cases:
        url = base_url + endpoint
        success = test_health_endpoint(url, user_agent, method)
        results.append(success)
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("=" * 50)
    print(f"RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ ALL HEALTH CHECKS PASSED - READY FOR DEPLOYMENT")
        sys.exit(0)
    else:
        print("❌ SOME HEALTH CHECKS FAILED - DEPLOYMENT MAY FAIL")
        sys.exit(1)

if __name__ == '__main__':
    main()