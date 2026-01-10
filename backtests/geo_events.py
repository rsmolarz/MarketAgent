"""
Historical geopolitical events for backtesting GeopoliticalRiskAgent.

Event-impact backtesting approach:
- Layer 1: Known geopolitical event dates with region/severity
- Layer 2: Market reaction measured via SPY/VIX forward returns

Sources for expanding this dataset:
- GDELT (Global Database of Events, Language, and Tone)
- ACLED (Armed Conflict Location & Event Data)
- ICEWS (Integrated Crisis Early Warning System)
"""
from datetime import date

HISTORICAL_GEO_EVENTS = [
    # 2008 Financial Crisis context
    {"date": date(2008, 8, 8), "region": "Russia-Georgia", "risk_score": 75, "keywords": ["War", "Invasion", "Military"]},
    
    # 2011 Arab Spring
    {"date": date(2011, 1, 25), "region": "Middle East", "risk_score": 70, "keywords": ["Protest", "Revolution", "Crisis"]},
    {"date": date(2011, 3, 15), "region": "Middle East", "risk_score": 80, "keywords": ["Civil War", "Violence", "Conflict"]},
    
    # 2013 Syria chemical weapons
    {"date": date(2013, 8, 21), "region": "Middle East", "risk_score": 85, "keywords": ["Chemical", "Attack", "Military"]},
    
    # 2014 Crimea annexation
    {"date": date(2014, 2, 27), "region": "Ukraine", "risk_score": 80, "keywords": ["Troops", "Annexation", "Crisis"]},
    {"date": date(2014, 3, 18), "region": "Ukraine", "risk_score": 85, "keywords": ["Invasion", "Sanctions", "Conflict"]},
    
    # 2015 China market turmoil
    {"date": date(2015, 8, 24), "region": "China-US", "risk_score": 65, "keywords": ["Market", "Crisis", "Tension"]},
    
    # 2016 Brexit vote
    {"date": date(2016, 6, 24), "region": "Europe", "risk_score": 70, "keywords": ["Brexit", "Crisis", "Uncertainty"]},
    
    # 2017 North Korea tensions
    {"date": date(2017, 8, 8), "region": "North Korea", "risk_score": 80, "keywords": ["Nuclear", "Missile", "Threat"]},
    {"date": date(2017, 9, 3), "region": "North Korea", "risk_score": 85, "keywords": ["Nuclear", "Test", "Escalation"]},
    
    # 2018 Trade war
    {"date": date(2018, 3, 22), "region": "China-US", "risk_score": 70, "keywords": ["Tariff", "Trade", "Conflict"]},
    {"date": date(2018, 7, 6), "region": "China-US", "risk_score": 75, "keywords": ["Trade War", "Sanctions", "Escalation"]},
    
    # 2019 Hong Kong protests
    {"date": date(2019, 6, 9), "region": "China-US", "risk_score": 65, "keywords": ["Protest", "Hong Kong", "Crisis"]},
    {"date": date(2019, 11, 19), "region": "China-US", "risk_score": 70, "keywords": ["Protest", "Violence", "Tension"]},
    
    # 2020 Iran tensions
    {"date": date(2020, 1, 3), "region": "Middle East", "risk_score": 90, "keywords": ["Airstrike", "Assassination", "War"]},
    {"date": date(2020, 1, 8), "region": "Middle East", "risk_score": 85, "keywords": ["Missile", "Retaliation", "Escalation"]},
    
    # 2021 Capitol riot
    {"date": date(2021, 1, 6), "region": "US Domestic", "risk_score": 70, "keywords": ["Riot", "Violence", "Crisis"]},
    
    # 2022 Russia-Ukraine war
    {"date": date(2022, 2, 24), "region": "Ukraine", "risk_score": 95, "keywords": ["War", "Invasion", "Missiles", "Sanctions"]},
    {"date": date(2022, 3, 1), "region": "Ukraine", "risk_score": 90, "keywords": ["War", "Shelling", "Nuclear"]},
    {"date": date(2022, 9, 21), "region": "Ukraine", "risk_score": 85, "keywords": ["Mobilization", "Nuclear", "Escalation"]},
    
    # 2023 Israel-Hamas conflict
    {"date": date(2023, 10, 7), "region": "Middle East", "risk_score": 95, "keywords": ["Attack", "War", "Terror", "Hostages"]},
    {"date": date(2023, 10, 13), "region": "Middle East", "risk_score": 90, "keywords": ["Invasion", "Bombing", "Escalation"]},
    {"date": date(2023, 10, 27), "region": "Middle East", "risk_score": 85, "keywords": ["Ground Invasion", "Conflict", "Casualties"]},
    
    # 2024 Houthi attacks
    {"date": date(2024, 1, 11), "region": "Middle East", "risk_score": 80, "keywords": ["Airstrike", "Red Sea", "Shipping"]},
    {"date": date(2024, 2, 3), "region": "Middle East", "risk_score": 75, "keywords": ["Strike", "Yemen", "Escalation"]},
    
    # 2024 Taiwan tensions
    {"date": date(2024, 1, 13), "region": "Taiwan", "risk_score": 70, "keywords": ["Election", "China", "Tension"]},
    {"date": date(2024, 5, 23), "region": "Taiwan", "risk_score": 75, "keywords": ["Military", "Drills", "Escalation"]},
]


def get_events_for_date(target_date: date) -> list:
    """Get all events for a specific date."""
    return [e for e in HISTORICAL_GEO_EVENTS if e["date"] == target_date]


def get_all_event_dates() -> list:
    """Get all unique event dates."""
    return sorted(set(e["date"] for e in HISTORICAL_GEO_EVENTS))
