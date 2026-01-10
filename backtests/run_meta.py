#!/usr/bin/env python3
"""
End-to-end Meta-Agent runner.
Loads backtest results, labels with forward returns, computes metrics,
ranks agents, and updates the schedule.
"""
import json
import logging
from pathlib import Path

from backtests.evaluator import label_forward_returns
from backtests.agent_metrics import aggregate_agent_metrics, save_agent_metrics, load_agent_metrics
from backtests.meta_agent import rank_agents, format_ranking_report, get_capital_allocation
from backtests.registry import update_schedule
from backtests.data_yahoo import load_cached_frame

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_findings_from_jsonl(path: str) -> list:
    """Load findings from JSONL file."""
    findings = []
    with open(path, "r") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))
    return findings


def run_meta_agent(
    findings_path: str = "backtests/results_multi.jsonl",
    symbols: list = None,
    horizon: str = "ret_20d",
    save_metrics: bool = True,
    update_sched: bool = True,
) -> dict:
    """
    Full Meta-Agent pipeline:
    1. Load findings from backtest
    2. Load price data for symbols
    3. Label findings with forward returns
    4. Aggregate per-agent metrics
    5. Rank agents and make decisions
    6. Update schedule
    
    Args:
        findings_path: Path to JSONL file with backtest findings
        symbols: List of symbols to load prices for (auto-detected if None)
        horizon: Forward return horizon for ranking (e.g., "ret_20d")
        save_metrics: Whether to save per-agent metrics to files
        update_sched: Whether to update agent_schedule.json
    
    Returns:
        Dict with decisions, metrics, and allocation
    """
    # 1. Load findings
    logger.info(f"Loading findings from {findings_path}")
    findings = load_findings_from_jsonl(findings_path)
    logger.info(f"Loaded {len(findings)} findings")
    
    # 2. Detect symbols and load price frames
    if symbols is None:
        symbols = list(set(f.get("symbol") for f in findings if f.get("symbol")))
    
    logger.info(f"Loading price data for {len(symbols)} symbols")
    price_frames = {}
    for sym in symbols:
        try:
            df = load_cached_frame(sym)
            if df is not None and not df.empty:
                price_frames[sym] = df
        except Exception as e:
            logger.warning(f"Could not load prices for {sym}: {e}")
    
    logger.info(f"Loaded price frames for {len(price_frames)} symbols")
    
    # 3. Label forward returns
    labeled = label_forward_returns(findings, price_frames)
    logger.info(f"Labeled {len(labeled)} findings with forward returns")
    
    # 4. Aggregate metrics
    metrics = aggregate_agent_metrics(labeled)
    
    if save_metrics:
        save_agent_metrics(metrics)
    
    # 5. Rank agents
    decisions = rank_agents(metrics, horizon=horizon)
    
    # Print report
    report = format_ranking_report(decisions)
    print("\n" + report + "\n")
    
    # 6. Update schedule
    if update_sched:
        schedule = update_schedule(decisions)
        logger.info(f"Updated schedule with {len(schedule)} agent entries")
    
    # 7. Get capital allocation
    allocation = get_capital_allocation(decisions)
    
    return {
        "decisions": decisions,
        "metrics": metrics,
        "allocation": allocation,
        "labeled_count": len(labeled),
        "total_findings": len(findings),
    }


def run_from_existing_metrics(
    metrics_dir: str = "backtests/metrics",
    horizon: str = "ret_20d",
    update_sched: bool = True,
) -> dict:
    """
    Run Meta-Agent using pre-computed metrics files.
    Faster when you don't need to re-label findings.
    """
    logger.info(f"Loading existing metrics from {metrics_dir}")
    metrics = load_agent_metrics(metrics_dir)
    
    if not metrics:
        logger.error("No metrics found")
        return {}
    
    decisions = rank_agents(metrics, horizon=horizon)
    
    report = format_ranking_report(decisions)
    print("\n" + report + "\n")
    
    if update_sched:
        update_schedule(decisions)
    
    allocation = get_capital_allocation(decisions)
    
    return {
        "decisions": decisions,
        "metrics": metrics,
        "allocation": allocation,
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Meta-Agent pipeline")
    parser.add_argument("--from-metrics", action="store_true", help="Use existing metrics files")
    parser.add_argument("--findings", default="backtests/results_multi.jsonl", help="Path to findings JSONL")
    parser.add_argument("--horizon", default="ret_20d", help="Forward return horizon for ranking")
    parser.add_argument("--no-save", action="store_true", help="Don't save metrics or update schedule")
    
    args = parser.parse_args()
    
    if args.from_metrics:
        result = run_from_existing_metrics(
            horizon=args.horizon,
            update_sched=not args.no_save,
        )
    else:
        result = run_meta_agent(
            findings_path=args.findings,
            horizon=args.horizon,
            save_metrics=not args.no_save,
            update_sched=not args.no_save,
        )
    
    print(f"\nMeta-Agent complete. {len(result.get('allocation', {}))} agents allocated capital.")
