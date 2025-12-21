from greatest_trade_agent import GreatestTradeAgent

def test_agent_runs():
    agent = GreatestTradeAgent()
    result = agent.run_full_analysis()
    assert "macro" in result and "cds" in result and "struct" in result
