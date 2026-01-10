#!/usr/bin/env python3
"""
Demo script for Distressed Property & Deal Evaluator Agents
============================================================
Run this to test the agents with sample data.
"""

import json
import sys
sys.path.insert(0, '.')

from datetime import datetime


def demo_distressed_property_agent():
    """Demo the DistressedPropertyAgent."""
    print("\n" + "=" * 60)
    print("🏠 DISTRESSED PROPERTY AGENT - DEMO")
    print("=" * 60)
    
    from agents.distressed_property_agent import DistressedPropertyAgent
    
    agent = DistressedPropertyAgent()
    
    # Run analysis (uses sample data since no APIs configured)
    signals = agent.analyze()
    
    print(f"\n📊 Generated {len(signals)} signals:\n")
    
    for sig in signals:
        print(f"  [{sig['signal_type'].upper()}] {sig['address']}, {sig['city']}, {sig['state']}")
        print(f"     Strength: {sig['signal_strength']:.0f}/100")
        print(f"     Price: ${sig['price']:,.0f} | Est. Value: ${sig['estimated_value']:,.0f}")
        print(f"     Discount: {sig['discount_pct']:.1f}% | Status: {sig['status']}")
        print()
    
    return signals


def demo_distressed_deal_evaluator():
    """Demo the DistressedDealEvaluatorAgent."""
    print("\n" + "=" * 60)
    print("📈 DISTRESSED DEAL EVALUATOR AGENT - DEMO")
    print("=" * 60)
    
    from agents.distressed_deal_evaluator_agent import DistressedDealEvaluatorAgent
    
    agent = DistressedDealEvaluatorAgent()
    
    # Run analysis
    signals = agent.analyze()
    
    print(f"\n📊 Evaluated {len(signals)} deals:\n")
    
    for sig in signals:
        print(f"  [{sig['signal_type'].upper()}] {sig['company_name']}")
        print(f"     Industry: {sig['industry']} | Distress: {sig['distress_level']}")
        print(f"     Altman Z-Score: {sig['altman_z_score']:.2f} | P(Default): {sig['probability_of_default']:.1%}")
        print(f"     Going Concern: ${sig['going_concern_value']:,.0f} | Liquidation: ${sig['liquidation_value']:,.0f}")
        print(f"     Fulcrum: {sig['fulcrum_security']} @ {sig['fulcrum_trading_price']:.0f}¢")
        print(f"     Expected IRR: {sig['expected_irr']:.1%} | Weighted Recovery: {sig['weighted_recovery']:.0f}%")
        print(f"     Signal Strength: {sig['signal_strength']:.0f}/100 | Risk/Reward: {sig['risk_reward_score']:.2f}x")
        print(f"     Thesis: {sig['thesis'][:100]}...")
        print()
        
        # Show scenario breakdown
        print("     Scenarios:")
        for scenario in sig['scenarios']:
            print(f"       • {scenario['scenario_name']}: {scenario['probability']:.0%} prob, "
                  f"${scenario['enterprise_value']:,.0f} EV, {scenario['timeline_months']}mo")
        print()
    
    return signals


def demo_single_deal_evaluation():
    """Demo evaluating a single custom deal."""
    print("\n" + "=" * 60)
    print("🔍 SINGLE DEAL EVALUATION - CUSTOM INPUT")
    print("=" * 60)
    
    from agents.distressed_deal_evaluator_agent import DistressedDealEvaluatorAgent
    
    agent = DistressedDealEvaluatorAgent()
    
    # Custom deal to evaluate
    custom_deal = {
        "deal_id": "custom-001",
        "company_name": "TechStartup Inc",
        "industry": "technology",
        "total_assets": 100_000_000,
        "current_assets": 40_000_000,
        "current_liabilities": 35_000_000,
        "retained_earnings": -20_000_000,
        "ebit": -5_000_000,
        "ebitda": 2_000_000,
        "market_cap": 10_000_000,
        "total_liabilities": 80_000_000,
        "revenue": 50_000_000,
        "total_debt": 70_000_000,
        "secured_debt": 40_000_000,
        "senior_unsecured": 30_000_000,
        "secured_price": 85,
        "unsecured_price": 35,
        "cash": 15_000_000,
        "accounts_receivable": 20_000_000,
        "inventory": 5_000_000,
        "ppe": 30_000_000,
        "in_bankruptcy": False,
        "source": "custom_input"
    }
    
    print(f"\nEvaluating: {custom_deal['company_name']}")
    print(f"Total Debt: ${custom_deal['total_debt']:,}")
    print(f"EBITDA: ${custom_deal['ebitda']:,}")
    
    evaluation = agent.evaluate_deal(custom_deal)
    
    if evaluation:
        print(f"\n📋 EVALUATION RESULTS:")
        print(f"   Distress Level: {evaluation.distress_level}")
        print(f"   Altman Z-Score: {evaluation.altman_z_score}")
        print(f"   P(Default): {evaluation.probability_of_default:.1%}")
        print(f"   Going Concern Value: ${evaluation.going_concern_value:,.0f}")
        print(f"   Liquidation Value: ${evaluation.liquidation_value:,.0f}")
        print(f"   Fulcrum Security: {evaluation.fulcrum_security}")
        print(f"   Expected IRR: {evaluation.expected_irr:.1%}")
        print(f"   Signal: {evaluation.signal_type.upper()} (strength: {evaluation.signal_strength:.0f})")
        print(f"\n   Thesis: {evaluation.thesis}")
    
    return evaluation


def run_offline_eval():
    """Run offline evaluation to verify output schemas."""
    print("\n" + "=" * 60)
    print("🧪 OFFLINE EVAL - SCHEMA VALIDATION")
    print("=" * 60)
    
    from eval.adapters_distressed import (
        run_distressed_property_offline,
        run_distressed_deal_evaluator_offline,
        DISTRESSED_PROPERTY_SCHEMA,
        DISTRESSED_DEAL_SCHEMA
    )
    
    # Test property agent
    property_results = run_distressed_property_offline({})
    print(f"\n✓ Property Agent: {len(property_results)} fixture signals")
    
    # Validate schema
    required_keys = DISTRESSED_PROPERTY_SCHEMA["item"]["required_keys"]
    for result in property_results:
        missing = [k for k in required_keys if k not in result]
        if missing:
            print(f"  ✗ Missing keys: {missing}")
        else:
            print(f"  ✓ {result['property_id']}: all required keys present")
    
    # Test deal evaluator
    deal_results = run_distressed_deal_evaluator_offline({})
    print(f"\n✓ Deal Evaluator: {len(deal_results)} fixture signals")
    
    required_keys = DISTRESSED_DEAL_SCHEMA["item"]["required_keys"]
    for result in deal_results:
        missing = [k for k in required_keys if k not in result]
        if missing:
            print(f"  ✗ Missing keys: {missing}")
        else:
            print(f"  ✓ {result['deal_id']}: all required keys present")
    
    print("\n✅ Schema validation complete")


def main():
    print("\n" + "=" * 60)
    print("DISTRESSED AGENTS - FULL DEMO")
    print("=" * 60)
    
    # Run all demos
    demo_distressed_property_agent()
    demo_distressed_deal_evaluator()
    demo_single_deal_evaluation()
    run_offline_eval()
    
    print("\n" + "=" * 60)
    print("✅ ALL DEMOS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
