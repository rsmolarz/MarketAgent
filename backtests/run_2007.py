from __future__ import annotations

from backtests.data_yahoo import fetch_daily
from backtests.runner import run_backtest_for_agents


def main():
    start = "2007-01-01"
    end = "2026-01-08"

    symbols = ["SPY", "QQQ", "IWM", "DIA", "^VIX", "^TNX", "TLT"]
    print(f"Fetching data for {symbols} from {start} to {end}...")
    data = fetch_daily(symbols, start=start, end=end)
    print(f"Fetched data for {len(data)} symbols")

    agents = [
        ("agents.market_correction_agent", "MarketCorrectionAgent"),
        ("agents.equity_momentum_agent", "EquityMomentumAgent"),
        ("agents.bond_stress_agent", "BondStressAgent"),
    ]

    print(f"Running backtest for {len(agents)} agents...")
    summary = run_backtest_for_agents(
        agents=agents,
        data=data,
        symbols=symbols,
        start=start,
        end=end,
        lookback=252,
        output_jsonl="backtests/results_2007.jsonl",
    )

    print("\n=== Backtest Summary ===")
    print(f"Period: {summary['start']} to {summary['end']}")
    print(f"Trading days: {summary['days']}")
    print(f"Total signals: {summary['rows']}")
    print(f"Skipped agents: {summary['skipped_agents']}")
    print(f"Output: {summary['output']}")


if __name__ == "__main__":
    main()
