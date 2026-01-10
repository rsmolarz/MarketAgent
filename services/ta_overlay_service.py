"""
TA Overlay Service
Returns JSON for dashboard chart (candles + RSI + signal markers)
"""
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd
import numpy as np
import logging

from data_sources.yahoo_finance_client import YahooFinanceClient
from ta.indicators import rsi, macd, bollinger, ma

logger = logging.getLogger(__name__)

DEFAULT_SYMBOL = "SPY"


def _clean_nan(val):
    """Convert NaN/inf to None for JSON serialization."""
    if val is None:
        return None
    try:
        if np.isnan(val) or np.isinf(val):
            return None
    except (TypeError, ValueError):
        pass
    return float(val)


def _clean_list(lst: list) -> list:
    """Clean a list of potential NaN/inf values."""
    return [_clean_nan(v) for v in lst]


def _df_to_ohlc(df: pd.DataFrame) -> Dict[str, list]:
    """Convert DataFrame to OHLC JSON"""
    df = df.dropna(subset=['Close']).copy()
    idx = df.index
    ts = [x.isoformat() if hasattr(x, "isoformat") else str(x) for x in idx]
    return {
        "t": ts,
        "open": _clean_list(df["Open"].astype(float).tolist()),
        "high": _clean_list(df["High"].astype(float).tolist()),
        "low": _clean_list(df["Low"].astype(float).tolist()),
        "close": _clean_list(df["Close"].astype(float).tolist()),
        "volume": (_clean_list(df["Volume"].astype(float).tolist()) if "Volume" in df.columns else []),
    }


def _safe_fill(series: pd.Series) -> pd.Series:
    """Safe fillna that works across pandas versions"""
    result = series.copy()
    result = result.bfill()
    result = result.ffill()
    return result


def _compute_ta(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute all TA indicators for chart"""
    close = df["Close"].astype(float)
    out = {}

    out["rsi14"] = _clean_list(rsi(close, 14).fillna(50.0).astype(float).tolist())

    macd_line, signal_line, hist = macd(close)
    out["macd"] = _clean_list(macd_line.fillna(0.0).astype(float).tolist())
    out["macd_signal"] = _clean_list(signal_line.fillna(0.0).astype(float).tolist())
    out["macd_hist"] = _clean_list(hist.fillna(0.0).astype(float).tolist())

    ma20, bb_u, bb_l = bollinger(close, 20, 2.0)
    out["ma20"] = _clean_list(_safe_fill(ma20).astype(float).tolist())
    out["bb_u"] = _clean_list(_safe_fill(bb_u).astype(float).tolist())
    out["bb_l"] = _clean_list(_safe_fill(bb_l).astype(float).tolist())

    out["ma50"] = _clean_list(_safe_fill(ma(close, 50)).astype(float).tolist())
    out["ma200"] = _clean_list(_safe_fill(ma(close, 200)).astype(float).tolist())

    return out


def _find_markers_from_findings(findings: List[dict], symbol: str) -> List[dict]:
    """Convert Finding rows into marker points for the chart"""
    markers = []
    for f in findings:
        f_symbol = (f.get("symbol") or "").upper()
        if f_symbol != symbol.upper():
            continue
        ts = f.get("timestamp")
        if not ts:
            continue
        sev = f.get("severity", "medium")
        markers.append({
            "t": ts,
            "title": f.get("title", "Signal"),
            "severity": sev,
            "confidence": float(f.get("confidence") or 0.5),
            "agent": f.get("agent_name") or f.get("agent") or "Unknown",
        })
    return markers


def build_ta_overlay(symbol: str, period: str, findings: List[dict]) -> Dict[str, Any]:
    """Build complete TA overlay data for charting"""
    try:
        yahoo = YahooFinanceClient()
        df = yahoo.get_price_data(symbol, period=period)
        if df is None or df.empty or len(df) < 60:
            return {"ok": False, "reason": "insufficient_price_data"}

        ohlc = _df_to_ohlc(df)
        ta = _compute_ta(df)
        markers = _find_markers_from_findings(findings, symbol)

        return {
            "ok": True,
            "symbol": symbol,
            "period": period,
            "ohlc": ohlc,
            "ta": ta,
            "markers": markers,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"TA overlay error for {symbol}: {e}")
        return {"ok": False, "reason": str(e)}
