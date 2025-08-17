#!/usr/bin/env python3
"""
Minimal test to verify if the simple route works
"""
import requests

try:
    response = requests.get('http://localhost:5000/simple', timeout=10)
    print(f"HTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        content = response.text
        print(f"Response length: {len(content)} characters")
        
        # Check for key indicators
        if "findings loaded from database" in content.lower():
            print("✅ SUCCESS: Found findings indicator")
        elif "no findings" in content.lower():
            print("❌ WARNING: No findings message found")
        else:
            print("❌ ERROR: No clear status message")
            
        # Print first 500 chars
        print("\nFirst 500 characters of response:")
        print(content[:500])
        
    else:
        print(f"❌ ERROR: HTTP {response.status_code}")
        
except Exception as e:
    print(f"❌ EXCEPTION: {e}")