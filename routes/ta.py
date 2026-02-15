"""
Technical Analysis API endpoints for dashboard overlays.
"""
from flask import Blueprint, jsonify, request
from data_sources.price_loader import load_symbol_frame
from ta.ta_engine import rsi, ta_vote, get_ta_signals
import numpy as np

ta_bp = Blueprint("ta", __name__)


def _clean_nan(val):
    """Convert NaN to None for JSON serialization."""
    if isinstance(val, float) and np.isnan(val):
        return None
    return val


def _clean_list(lst):
    """Clean a list of potential NaN values."""
    return [_clean_nan(v) for v in lst]


@ta_bp.route("/api/ta/<symbol>")
def ta_data(symbol):
    """
    Get TA data for a symbol (prices, RSI).
    Used by dashboard for chart overlays.
    """
    df = load_symbol_frame(symbol)

    if df.empty:
        return jsonify({"ok": False, "reason": "no_data"})

    df = df.tail(300)

    rsi_series = rsi(df["Close"]).fillna(50)

    return jsonify({
        "ok": True,
        "symbol": symbol,
        "dates": df.index.strftime("%Y-%m-%d").tolist(),
        "close": _clean_list(df["Close"].round(2).tolist()),
        "rsi": _clean_list(rsi_series.round(1).tolist()),
    })


@ta_bp.route("/api/ta/<symbol>/vote")
def ta_vote_endpoint(symbol):
    """
    Get TA vote (ACT/WATCH/IGNORE) for a symbol.
    """
    df = load_symbol_frame(symbol)
    
    if df.empty:
        return jsonify({
            "ok": False,
            "vote": "WATCH",
            "reason": "no_data"
        })
    
    result = ta_vote(df)
    result["ok"] = True
    result["symbol"] = symbol
    
    return jsonify(result)


@ta_bp.route("/api/ta/<symbol>/signals")
def ta_signals_endpoint(symbol):
    """
    Get comprehensive TA signals for a symbol.
    """
    df = load_symbol_frame(symbol)
    
    result = get_ta_signals(df, symbol)
    result["ok"] = not df.empty
    
    indicators = result.get("indicators", {})
    for k, v in indicators.items():
        indicators[k] = _clean_nan(v)
    
    return jsonify(result)


@ta_bp.route("/api/ta/batch", methods=["POST"])
def ta_batch():
    """
    Get TA data for multiple symbols.
    """
    data = request.get_json() or {}
    symbols = data.get("symbols", [])
    
    if not symbols:
        return jsonify({"ok": False, "reason": "no_symbols"})
    
    results = {}
    for symbol in symbols[:10]:
        df = load_symbol_frame(symbol)
        if df.empty:
            results[symbol] = {"ok": False}
            continue
        
        vote = ta_vote(df)
        results[symbol] = {
            "ok": True,
            "vote": vote.get("vote"),
            "score": vote.get("score"),
            "reason": vote.get("reason"),
        }
    
    return jsonify({"ok": True, "results": results})
