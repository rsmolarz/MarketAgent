#!/usr/bin/env python3
"""
Debug script to verify market data directly from database
"""
import sys
import os
sys.path.append('.')

from app import create_app
from models import Finding
from datetime import datetime

app = create_app()

with app.app_context():
    try:
        # Query database directly
        findings = Finding.query.order_by(Finding.timestamp.desc()).limit(10).all()
        
        print(f"=== DIRECT DATABASE VERIFICATION ===")
        print(f"Total findings in database: {Finding.query.count()}")
        print(f"Recent findings (last 10):")
        
        for finding in findings:
            minutes_ago = int((datetime.utcnow() - finding.timestamp).total_seconds() / 60)
            print(f"  • {finding.title} - {minutes_ago}min ago ({finding.agent_name})")
        
        # Test API-style data
        findings_data = []
        for finding in findings:
            findings_data.append({
                'id': finding.id,
                'title': finding.title,
                'agent_name': finding.agent_name,
                'symbol': finding.symbol,
                'severity': finding.severity,
                'timestamp': finding.timestamp.isoformat() + 'Z'
            })
        
        print(f"\n=== API-STYLE DATA SAMPLE ===")
        if findings_data:
            print(f"Latest: {findings_data[0]['title']}")
            print(f"Agent: {findings_data[0]['agent_name']}")
            print(f"Symbol: {findings_data[0]['symbol']}")
        
        print(f"\n✅ Database contains {len(findings)} findings")
        print(f"✅ Data is accessible and properly formatted")
        
    except Exception as e:
        print(f"❌ Database error: {e}")