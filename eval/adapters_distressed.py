"""
Offline Eval Adapters for Distressed Agents
============================================
These adapters return fixture data for CI/CD evaluation.
No network calls, no external dependencies.
"""

from datetime import datetime
from typing import Dict, Any, List


def now():
    return datetime.utcnow().isoformat() + "Z"


def run_distressed_property_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Offline adapter for DistressedPropertyAgent.
    Returns fixture data matching canonical output shape.
    """
    return [
        {
            "property_id": "prop-12345",
            "address": "123 Foreclosure Lane",
            "city": "Phoenix",
            "state": "AZ",
            "signal_type": "deep_discount",
            "signal_strength": 78.5,
            "price": 185000.0,
            "estimated_value": 250000.0,
            "discount_pct": 26.0,
            "property_type": "single_family",
            "status": "foreclosure",
            "days_on_market": 45,
            "source": "fixture",
            "timestamp": now()
        },
        {
            "property_id": "prop-67890",
            "address": "456 Auction Drive",
            "city": "Las Vegas",
            "state": "NV",
            "signal_type": "auction_imminent",
            "signal_strength": 86.0,
            "price": 125000.0,
            "estimated_value": 160000.0,
            "discount_pct": 21.9,
            "property_type": "condo",
            "status": "auction",
            "days_on_market": 30,
            "source": "fixture",
            "timestamp": now()
        },
        {
            "property_id": "prop-11111",
            "address": "789 Short Sale Blvd",
            "city": "Denver",
            "state": "CO",
            "signal_type": "price_drop",
            "signal_strength": 65.2,
            "price": 320000.0,
            "estimated_value": 380000.0,
            "discount_pct": 15.8,
            "property_type": "townhouse",
            "status": "short-sale",
            "days_on_market": 90,
            "source": "fixture",
            "timestamp": now()
        }
    ]


def run_distressed_deal_evaluator_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Offline adapter for DistressedDealEvaluatorAgent.
    Returns fixture data matching canonical output shape.
    """
    return [
        {
            "deal_id": "deal-001",
            "company_name": "Acme Manufacturing Corp",
            "industry": "manufacturing",
            "distress_level": "distressed",
            "altman_z_score": 1.45,
            "probability_of_default": 0.42,
            "going_concern_value": 315000000,
            "liquidation_value": 210000000,
            "enterprise_value_midpoint": 262500000,
            "total_debt": 350000000,
            "fulcrum_security": "Senior Unsecured",
            "fulcrum_trading_price": 45.0,
            "implied_ev_from_fulcrum": 245000000,
            "scenarios": [
                {
                    "scenario_name": "going_concern_restructure",
                    "probability": 0.35,
                    "enterprise_value": 315000000,
                    "recovery_by_class": {
                        "Senior Secured": 100.0,
                        "Senior Unsecured": 57.5,
                        "Subordinated": 0.0,
                        "Equity": 0
                    },
                    "equity_value": 0,
                    "timeline_months": 12
                },
                {
                    "scenario_name": "section_363_sale",
                    "probability": 0.30,
                    "enterprise_value": 236250000,
                    "recovery_by_class": {
                        "Senior Secured": 100.0,
                        "Senior Unsecured": 18.1,
                        "Subordinated": 0.0,
                        "Equity": 0
                    },
                    "equity_value": 0,
                    "timeline_months": 9
                },
                {
                    "scenario_name": "contested_chapter_11",
                    "probability": 0.20,
                    "enterprise_value": 262500000,
                    "recovery_by_class": {
                        "Senior Secured": 100.0,
                        "Senior Unsecured": 31.3,
                        "Subordinated": 0.0,
                        "Equity": 0
                    },
                    "equity_value": 0,
                    "timeline_months": 24
                },
                {
                    "scenario_name": "chapter_7_liquidation",
                    "probability": 0.15,
                    "enterprise_value": 210000000,
                    "recovery_by_class": {
                        "Senior Secured": 100.0,
                        "Senior Unsecured": 5.0,
                        "Subordinated": 0.0,
                        "Equity": 0
                    },
                    "equity_value": 0,
                    "timeline_months": 18
                }
            ],
            "weighted_recovery": 35.4,
            "expected_irr": 0.267,
            "signal_type": "buy_debt",
            "signal_strength": 72.5,
            "risk_reward_score": 1.85,
            "thesis": "Acme Manufacturing Corp is currently distressed. The fulcrum security is Senior Unsecured. Expected IRR of 26.7% with weighted recovery of 35%. Best case (going_concern_restructure): 35% probability. Worst case (chapter_7_liquidation): 15% probability.",
            "source": "fixture",
            "timestamp": now()
        },
        {
            "deal_id": "deal-002",
            "company_name": "RetailCo Holdings",
            "industry": "retail",
            "distress_level": "bankruptcy",
            "altman_z_score": -0.82,
            "probability_of_default": 0.93,
            "going_concern_value": 180000000,
            "liquidation_value": 285000000,
            "enterprise_value_midpoint": 232500000,
            "total_debt": 600000000,
            "fulcrum_security": "Senior Secured",
            "fulcrum_trading_price": 78.0,
            "implied_ev_from_fulcrum": 312000000,
            "scenarios": [
                {
                    "scenario_name": "going_concern_restructure",
                    "probability": 0.15,
                    "enterprise_value": 180000000,
                    "recovery_by_class": {
                        "Senior Secured": 45.0,
                        "Senior Unsecured": 0.0,
                        "Subordinated": 0.0,
                        "Equity": 0
                    },
                    "equity_value": 0,
                    "timeline_months": 12
                },
                {
                    "scenario_name": "section_363_sale",
                    "probability": 0.40,
                    "enterprise_value": 250000000,
                    "recovery_by_class": {
                        "Senior Secured": 62.5,
                        "Senior Unsecured": 0.0,
                        "Subordinated": 0.0,
                        "Equity": 0
                    },
                    "equity_value": 0,
                    "timeline_months": 6
                },
                {
                    "scenario_name": "contested_chapter_11",
                    "probability": 0.20,
                    "enterprise_value": 232500000,
                    "recovery_by_class": {
                        "Senior Secured": 58.1,
                        "Senior Unsecured": 0.0,
                        "Subordinated": 0.0,
                        "Equity": 0
                    },
                    "equity_value": 0,
                    "timeline_months": 24
                },
                {
                    "scenario_name": "chapter_7_liquidation",
                    "probability": 0.25,
                    "enterprise_value": 285000000,
                    "recovery_by_class": {
                        "Senior Secured": 71.3,
                        "Senior Unsecured": 0.0,
                        "Subordinated": 0.0,
                        "Equity": 0
                    },
                    "equity_value": 0,
                    "timeline_months": 12
                }
            ],
            "weighted_recovery": 60.8,
            "expected_irr": -0.089,
            "signal_type": "avoid",
            "signal_strength": 55.0,
            "risk_reward_score": 0.72,
            "thesis": "RetailCo Holdings is currently bankruptcy. The fulcrum security is Senior Secured. Expected IRR of -8.9% with weighted recovery of 61%. Best case (chapter_7_liquidation): 25% probability. Worst case (going_concern_restructure): 15% probability.",
            "source": "fixture",
            "timestamp": now()
        }
    ]


# Schema validators for eval harness
DISTRESSED_PROPERTY_SCHEMA = {
    "type": "list",
    "item": {
        "type": "dict",
        "required_keys": [
            "property_id",
            "address", 
            "signal_type",
            "signal_strength",
            "price",
            "status"
        ]
    }
}

DISTRESSED_DEAL_SCHEMA = {
    "type": "list",
    "item": {
        "type": "dict",
        "required_keys": [
            "deal_id",
            "company_name",
            "distress_level",
            "expected_irr",
            "signal_type",
            "signal_strength",
            "fulcrum_security"
        ]
    }
}
