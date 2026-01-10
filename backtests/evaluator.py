"""
Forward-return labeling for backtest findings.
Adds realized returns at multiple horizons to each finding.
"""
from typing import List, Dict, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)

FORWARD_WINDOWS = [5, 10, 20, 60]  # trading days


def label_forward_returns(
    findings: List[Dict],
    price_frames: Dict[str, pd.DataFrame],
    windows: Optional[List[int]] = None,
) -> List[Dict]:
    """
    Adds forward returns to each finding.
    
    Args:
        findings: List of finding dicts with 'symbol' and 'timestamp' keys
        price_frames: Dict mapping symbol -> DataFrame with DatetimeIndex and 'Close' column
        windows: Forward windows in trading days (default: [5, 10, 20, 60])
    
    Returns:
        List of findings with 'forward_returns' dict added
    """
    if windows is None:
        windows = FORWARD_WINDOWS
    
    out = []
    labeled_count = 0
    
    for f in findings:
        symbol = f.get("symbol")
        if not symbol or symbol not in price_frames:
            continue
        
        df = price_frames[symbol]
        ts = pd.to_datetime(f.get("timestamp"))
        
        if ts is None:
            continue
        
        # Find the closest date in the index
        if ts not in df.index:
            # Try to find nearest date
            idx_pos = df.index.searchsorted(ts)
            if idx_pos >= len(df):
                continue
            ts = df.index[idx_pos]
        
        try:
            entry_price = float(df.loc[ts]["Close"])
        except (KeyError, TypeError):
            continue
        
        labels = {}
        
        for w in windows:
            future_idx = df.index.searchsorted(ts) + w
            if future_idx < len(df):
                future_price = float(df.iloc[future_idx]["Close"])
                labels[f"ret_{w}d"] = (future_price / entry_price) - 1.0
        
        if labels:
            f_copy = dict(f)
            f_copy["forward_returns"] = labels
            out.append(f_copy)
            labeled_count += 1
    
    logger.info(f"Labeled {labeled_count}/{len(findings)} findings with forward returns")
    return out


def label_findings_from_jsonl(
    jsonl_path: str,
    price_frames: Dict[str, pd.DataFrame],
) -> List[Dict]:
    """
    Load findings from JSONL file and label with forward returns.
    """
    import json
    from pathlib import Path
    
    findings = []
    with open(Path(jsonl_path), "r") as f:
        for line in f:
            if line.strip():
                findings.append(json.loads(line))
    
    return label_forward_returns(findings, price_frames)
