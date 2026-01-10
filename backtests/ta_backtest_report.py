"""
TA Backtest Report Generator
Compares TechnicalAnalysisAgent signals against SPY returns
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def load_backtest_results(filepath: str = "backtests/results_2007.jsonl") -> List[dict]:
    """Load backtest results from JSONL file"""
    results = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
    except FileNotFoundError:
        logger.warning(f"Backtest results file not found: {filepath}")
    except Exception as e:
        logger.error(f"Error loading backtest results: {e}")
    return results


def filter_ta_findings(results: List[dict]) -> List[dict]:
    """Filter to only TechnicalAnalysisAgent findings"""
    ta_findings = []
    for r in results:
        agent = r.get("agent_name") or r.get("agent", "")
        if "TechnicalAnalysis" in agent:
            ta_findings.append(r)
    return ta_findings


def compute_signal_returns(findings: List[dict], price_data: pd.DataFrame, 
                          forward_days: List[int] = [1, 5, 10, 20]) -> Dict[str, Any]:
    """
    Compute forward returns after each TA signal
    
    Args:
        findings: List of TA findings with timestamps
        price_data: SPY price DataFrame with 'Close' column
        forward_days: List of forward return periods
        
    Returns:
        Statistics about signal performance
    """
    if not findings or price_data is None or price_data.empty:
        return {"error": "insufficient_data"}
    
    signal_stats = {
        "total_signals": len(findings),
        "by_type": {},
        "by_bias": {"bullish": [], "bearish": []},
        "forward_returns": {str(d): [] for d in forward_days},
    }
    
    price_data = price_data.copy()
    price_data.index = pd.to_datetime(price_data.index)
    
    for finding in findings:
        ts = finding.get("timestamp")
        if not ts:
            continue
            
        try:
            if isinstance(ts, str):
                signal_date = pd.to_datetime(ts).normalize()
            else:
                signal_date = pd.to_datetime(ts).normalize()
        except Exception:
            continue
        
        meta = finding.get("metadata") or finding.get("finding_metadata") or {}
        signal_info = meta.get("signal") or {}
        signal_type = signal_info.get("type", "UNKNOWN")
        bias = signal_info.get("bias", "neutral")
        confidence = float(signal_info.get("confidence", 0.5))
        
        if signal_type not in signal_stats["by_type"]:
            signal_stats["by_type"][signal_type] = {
                "count": 0,
                "avg_confidence": 0,
                "returns": {str(d): [] for d in forward_days}
            }
        
        signal_stats["by_type"][signal_type]["count"] += 1
        
        try:
            if signal_date not in price_data.index:
                idx_loc = price_data.index.get_indexer([signal_date], method='nearest')[0]
                if idx_loc < 0 or idx_loc >= len(price_data):
                    continue
            else:
                idx_loc = price_data.index.get_loc(signal_date)
            
            entry_price = float(price_data.iloc[idx_loc]["Close"])
            
            for days in forward_days:
                exit_idx = idx_loc + days
                if exit_idx < len(price_data):
                    exit_price = float(price_data.iloc[exit_idx]["Close"])
                    ret = (exit_price / entry_price - 1) * 100
                    
                    if bias == "bearish":
                        ret = -ret
                    
                    signal_stats["forward_returns"][str(days)].append(ret)
                    signal_stats["by_type"][signal_type]["returns"][str(days)].append(ret)
                    
                    if bias in signal_stats["by_bias"]:
                        signal_stats["by_bias"][bias].append({
                            "type": signal_type,
                            "return": ret,
                            "days": days
                        })
                        
        except Exception as e:
            logger.debug(f"Return calculation error: {e}")
            continue
    
    summary = {
        "total_signals": signal_stats["total_signals"],
        "signal_types": {},
        "overall_performance": {},
    }
    
    for days_str, returns in signal_stats["forward_returns"].items():
        if returns:
            summary["overall_performance"][f"{days_str}d"] = {
                "mean_return": round(np.mean(returns), 3),
                "median_return": round(np.median(returns), 3),
                "std": round(np.std(returns), 3),
                "hit_rate": round(sum(1 for r in returns if r > 0) / len(returns) * 100, 1),
                "count": len(returns)
            }
    
    for signal_type, data in signal_stats["by_type"].items():
        type_summary = {"count": data["count"]}
        for days_str, returns in data["returns"].items():
            if returns:
                type_summary[f"{days_str}d_mean"] = round(np.mean(returns), 3)
                type_summary[f"{days_str}d_hit_rate"] = round(
                    sum(1 for r in returns if r > 0) / len(returns) * 100, 1
                )
        summary["signal_types"][signal_type] = type_summary
    
    return summary


def generate_ta_backtest_report(
    results_file: str = "backtests/results_2007.jsonl",
    spy_period: str = "max"
) -> Dict[str, Any]:
    """
    Generate comprehensive TA backtest report
    
    Returns report with:
    - Signal distribution
    - Forward returns by signal type
    - Comparison to buy-and-hold SPY
    - Best/worst performing signals
    """
    from data_sources.yahoo_finance_client import YahooFinanceClient
    
    results = load_backtest_results(results_file)
    ta_findings = filter_ta_findings(results)
    
    if not ta_findings:
        return {
            "ok": False,
            "reason": "no_ta_findings",
            "message": "No TechnicalAnalysisAgent findings in backtest results"
        }
    
    yahoo = YahooFinanceClient()
    spy_data = yahoo.get_price_data("SPY", period=spy_period)
    
    if spy_data is None or spy_data.empty:
        return {
            "ok": False,
            "reason": "no_spy_data",
            "message": "Could not fetch SPY price data"
        }
    
    signal_performance = compute_signal_returns(ta_findings, spy_data)
    
    spy_start = float(spy_data.iloc[0]["Close"])
    spy_end = float(spy_data.iloc[-1]["Close"])
    spy_buy_hold_return = (spy_end / spy_start - 1) * 100
    
    date_range = {
        "start": spy_data.index[0].isoformat() if hasattr(spy_data.index[0], 'isoformat') else str(spy_data.index[0]),
        "end": spy_data.index[-1].isoformat() if hasattr(spy_data.index[-1], 'isoformat') else str(spy_data.index[-1]),
    }
    
    report = {
        "ok": True,
        "generated_at": datetime.utcnow().isoformat(),
        "date_range": date_range,
        "spy_buy_hold_return": round(spy_buy_hold_return, 2),
        "total_ta_signals": len(ta_findings),
        "signal_performance": signal_performance,
        "benchmark_comparison": {},
    }
    
    overall = signal_performance.get("overall_performance", {})
    if "5d" in overall:
        ta_5d_mean = overall["5d"].get("mean_return", 0)
        report["benchmark_comparison"]["5d_vs_passive"] = {
            "ta_mean": ta_5d_mean,
            "outperforms": ta_5d_mean > 0,
        }
    
    if "20d" in overall:
        ta_20d_mean = overall["20d"].get("mean_return", 0)
        report["benchmark_comparison"]["20d_vs_passive"] = {
            "ta_mean": ta_20d_mean,
            "outperforms": ta_20d_mean > 0,
        }
    
    return report


def save_report(report: Dict[str, Any], filepath: str = "backtests/ta_report.json"):
    """Save report to JSON file"""
    with open(filepath, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"TA backtest report saved to {filepath}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    report = generate_ta_backtest_report()
    print(json.dumps(report, indent=2, default=str))
    if report.get("ok"):
        save_report(report)
