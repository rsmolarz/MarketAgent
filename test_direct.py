#!/usr/bin/env python3
"""
Test direct access to findings route to verify server-side rendering
"""
import requests
import sys
from bs4 import BeautifulSoup

try:
    # Test the findings route directly
    response = requests.get('http://localhost:5000/findings')
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for the success alert with market data
        success_alert = soup.find('div', class_='alert alert-success')
        if success_alert and 'Live Market Data Loaded' in success_alert.text:
            print("✅ SUCCESS: Server-side rendering working!")
            print(f"Found: {success_alert.text.strip()}")
            
            # Count finding items
            finding_items = soup.find_all('div', class_='finding-item')
            print(f"✅ Found {len(finding_items)} finding items in HTML")
            
            if finding_items:
                first_finding = finding_items[0]
                title = first_finding.find('h6')
                if title:
                    print(f"✅ First finding: {title.text.strip()}")
                    
        else:
            # Look for warning alert (no data)
            warning_alert = soup.find('div', class_='alert alert-warning')
            if warning_alert:
                print("❌ WARNING: No market data found")
                print(f"Message: {warning_alert.text.strip()}")
            else:
                print("❌ ERROR: No alerts found - template may not be rendering correctly")
                
        # Check for any error alerts
        error_alert = soup.find('div', class_='alert alert-danger')
        if error_alert:
            print(f"❌ ERROR ALERT: {error_alert.text.strip()}")
            
    else:
        print(f"❌ ERROR: HTTP {response.status_code}")
        print(response.text[:500])
        
except Exception as e:
    print(f"❌ EXCEPTION: {e}")
    sys.exit(1)