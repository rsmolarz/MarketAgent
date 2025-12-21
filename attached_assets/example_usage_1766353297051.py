from greatest_trade_agent import GreatestTradeAgent

if __name__ == "__main__":
    agent = GreatestTradeAgent(execution_hook=lambda a: print(f"EXECUTING: {a}"))
    signal = agent.run_full_analysis()
    print(signal)
