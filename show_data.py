#!/usr/bin/env python3
"""
Direct data display script to bypass all web interface issues
"""
import sys
sys.path.append('.')

from app import create_app
from models import Finding
from datetime import datetime
import json

app = create_app()

print("=== DIRECT MARKET DATA ACCESS ===")
print("Bypassing all web interface issues...")
print()

with app.app_context():
    try:
        # Get all findings
        all_findings = Finding.query.order_by(Finding.timestamp.desc()).all()
        recent_findings = [f for f in all_findings if (datetime.utcnow() - f.timestamp).total_seconds() < 3600]  # Last hour
        
        print(f"DATABASE ANALYSIS:")
        print(f"✅ Total findings in database: {len(all_findings)}")
        print(f"✅ Recent findings (last hour): {len(recent_findings)}")
        print()
        
        if all_findings:
            print("LATEST 5 FINDINGS:")
            for i, finding in enumerate(all_findings[:5], 1):
                minutes_ago = int((datetime.utcnow() - finding.timestamp).total_seconds() / 60)
                print(f"{i}. {finding.title}")
                print(f"   🤖 Agent: {finding.agent_name}")
                print(f"   📈 Symbol: {finding.symbol or 'N/A'}")
                print(f"   ⚠️  Severity: {finding.severity}")
                print(f"   🕐 Time: {minutes_ago} minutes ago")
                print(f"   📝 Description: {finding.description}")
                print()
            
            # Show agent activity
            agents = {}
            for finding in all_findings:
                agent = finding.agent_name
                if agent not in agents:
                    agents[agent] = 0
                agents[agent] += 1
            
            print("AGENT ACTIVITY:")
            for agent, count in sorted(agents.items(), key=lambda x: x[1], reverse=True):
                print(f"  • {agent}: {count} findings")
            print()
            
            # Show symbols
            symbols = {}
            for finding in all_findings:
                symbol = finding.symbol or 'N/A'
                if symbol not in symbols:
                    symbols[symbol] = 0
                symbols[symbol] += 1
            
            print("TRACKED SYMBOLS:")
            for symbol, count in sorted(symbols.items(), key=lambda x: x[1], reverse=True):
                print(f"  • {symbol}: {count} findings")
            print()
            
            print("✅ CONCLUSION: Market data is working and available!")
            print("✅ The backend system is generating findings successfully")
            print("✅ The issue is likely with the web frontend display")
            
        else:
            print("❌ NO FINDINGS FOUND")
            print("❌ Database is empty or not accessible")
            
    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        print("❌ Cannot access the database")

print("\n" + "="*50)
print("This data should be visible in the web interface.")
print("If you can see this data but not on the website,")
print("the problem is with frontend display, not data generation.")
print("="*50)