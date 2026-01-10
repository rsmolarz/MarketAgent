from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

from backtests.data_yahoo import fetch_daily


def load_signals(jsonl_path: str) -> pd.DataFrame:
    """Load backtest results from JSONL file."""
    rows = []
    with open(jsonl_path, "r") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def evaluate_correction_signals(
    signals_df: pd.DataFrame,
    price_data: Dict[str, pd.DataFrame],
    forward_days: List[int] = [20, 60, 120],
    correction_threshold: float = -0.10,
) -> Dict[str, Any]:
    """
    Evaluate correction signals against forward returns.
    
    Metrics computed:
    - Forward return @ 20/60/120 days
    - Max drawdown after signal
    - Hit rate (% signals followed by >= correction_threshold decline)
    - Lead time (days until correction)
    """
    
    results = {
        "total_signals": len(signals_df),
        "by_severity": {},
        "by_symbol": {},
        "forward_returns": {f"{d}d": [] for d in forward_days},
        "max_drawdowns": [],
        "hits": [],
        "lead_times": [],
    }
    
    if signals_df.empty:
        return results
    
    signals_df["asof_dt"] = pd.to_datetime(signals_df["asof"])
    
    for _, row in signals_df.iterrows():
        symbol = row.get("symbol")
        if not symbol or symbol not in price_data:
            continue
        
        df = price_data[symbol]
        if df.empty or "Close" not in df.columns:
            continue
        
        signal_date = row["asof_dt"]
        
        try:
            idx = df.index.get_indexer([signal_date], method="ffill")[0]
            if idx < 0:
                continue
            
            signal_price = float(df["Close"].iloc[idx])
            
            for fwd in forward_days:
                fwd_idx = idx + fwd
                if fwd_idx < len(df):
                    fwd_price = float(df["Close"].iloc[fwd_idx])
                    fwd_return = (fwd_price - signal_price) / signal_price
                    results["forward_returns"][f"{fwd}d"].append(fwd_return)
            
            window_end = min(idx + 252, len(df))
            future_prices = df["Close"].iloc[idx:window_end].astype(float)
            if len(future_prices) > 0:
                rolling_min = future_prices.cummin()
                drawdowns = (rolling_min - signal_price) / signal_price
                max_dd = float(drawdowns.min())
                results["max_drawdowns"].append(max_dd)
                
                hit = max_dd <= correction_threshold
                results["hits"].append(hit)
                
                if hit:
                    correction_idx = (drawdowns <= correction_threshold).idxmax()
                    if pd.notna(correction_idx):
                        lead_time = (correction_idx - df.index[idx]).days
                        results["lead_times"].append(lead_time)
        
        except Exception:
            continue
    
    summary = {
        "total_signals": results["total_signals"],
        "forward_returns": {},
        "hit_rate": None,
        "avg_max_drawdown": None,
        "avg_lead_time": None,
    }
    
    for fwd, returns in results["forward_returns"].items():
        if returns:
            arr = np.array(returns)
            summary["forward_returns"][fwd] = {
                "mean": float(np.mean(arr)),
                "median": float(np.median(arr)),
                "std": float(np.std(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "n": len(arr),
            }
    
    if results["hits"]:
        summary["hit_rate"] = float(np.mean(results["hits"]))
    
    if results["max_drawdowns"]:
        summary["avg_max_drawdown"] = float(np.mean(results["max_drawdowns"]))
    
    if results["lead_times"]:
        summary["avg_lead_time"] = float(np.mean(results["lead_times"]))
        summary["median_lead_time"] = float(np.median(results["lead_times"]))
    
    severity_counts = signals_df["severity"].value_counts().to_dict()
    summary["by_severity"] = {k: int(v) for k, v in severity_counts.items()}
    
    symbol_counts = signals_df["symbol"].value_counts().to_dict()
    summary["by_symbol"] = {str(k): int(v) for k, v in symbol_counts.items()}
    
    return summary


def evaluate_per_agent(signals_df: pd.DataFrame, price_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Evaluate each agent separately and save per-agent metrics."""
    agents = signals_df["agent"].unique()
    per_agent = {}
    
    for agent_name in agents:
        agent_signals = signals_df[signals_df["agent"] == agent_name]
        metrics = evaluate_correction_signals(agent_signals, price_data)
        per_agent[agent_name] = metrics
        
        metrics_path = Path(f"backtests/metrics/{agent_name}.json")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        print(f"Saved: {metrics_path}")
    
    return per_agent


def main():
    jsonl_path = "backtests/results_2007.jsonl"
    
    if not Path(jsonl_path).exists():
        print(f"No results file found at {jsonl_path}")
        print("Run: python backtests/run_2007.py first")
        return
    
    print("Loading signals...")
    signals_df = load_signals(jsonl_path)
    print(f"Loaded {len(signals_df)} signals")
    
    print("\nFetching price data for evaluation...")
    symbols = ["SPY", "QQQ", "IWM", "DIA", "^VIX", "^TNX", "TLT"]
    price_data = fetch_daily(symbols, start="2007-01-01", end="2026-12-31")
    
    print("\nEvaluating per-agent metrics...")
    per_agent = evaluate_per_agent(signals_df, price_data)
    
    print("\nEvaluating all signals...")
    results = evaluate_correction_signals(
        signals_df,
        price_data,
        forward_days=[20, 60, 120],
        correction_threshold=-0.10,
    )
    results["per_agent"] = {k: {"signal_count": v["total_signals"], "hit_rate": v.get("hit_rate")} for k, v in per_agent.items()}
    
    print("\n" + "=" * 60)
    print("CORRECTION SIGNAL EVALUATION")
    print("=" * 60)
    print(f"Total signals: {results['total_signals']}")
    print(f"\nBy severity: {results['by_severity']}")
    print(f"\nBy symbol: {results['by_symbol']}")
    
    if results["hit_rate"] is not None:
        print(f"\nHit rate (>= 10% decline after signal): {results['hit_rate']*100:.1f}%")
    
    if results["avg_max_drawdown"] is not None:
        print(f"Average max drawdown after signal: {results['avg_max_drawdown']*100:.1f}%")
    
    if results.get("avg_lead_time") is not None:
        print(f"Average lead time to correction: {results['avg_lead_time']:.0f} days")
        print(f"Median lead time to correction: {results.get('median_lead_time', 0):.0f} days")
    
    print("\nForward returns after signals:")
    for period, stats in results["forward_returns"].items():
        if stats:
            print(f"  {period}: mean={stats['mean']*100:.2f}%, median={stats['median']*100:.2f}%, n={stats['n']}")
    
    print("\nPer-agent breakdown:")
    for agent, data in results["per_agent"].items():
        hr = f"{data['hit_rate']*100:.1f}%" if data.get('hit_rate') else "N/A"
        print(f"  {agent}: {data['signal_count']} signals, hit_rate={hr}")
    
    output_path = "backtests/eval_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results saved to: {output_path}")


if __name__ == "__main__":
    main()
