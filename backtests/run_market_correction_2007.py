from __future__ import annotations
from backtests.data_yahoo import fetch_daily
from backtests.runner import run_backtest_for_agents

def main():
    start = "2007-01-01"
    end = "2026-01-10"

    symbols = ["SPY", "QQQ", "IWM", "DIA", "^VIX", "TLT", "^TNX"]
    data = fetch_daily(symbols, start=start, end=end)

    agents = [
        ("agents.market_correction_agent", "MarketCorrectionAgent"),
    ]

    summary = run_backtest_for_agents(
        agents=agents,
        data=data,
        symbols=symbols,
        start=start,
        end=end,
        lookback=252,
        output_jsonl="backtests/market_correction_findings_2007.jsonl",
    )
    print(summary)

if __name__ == "__main__":
    main()
