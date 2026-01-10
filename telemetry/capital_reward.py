from typing import Any, Dict, Optional


def capital_weighted_reward(
    agent: str,
    output: Any,
    *,
    capital_usd: float,
    max_loss_usd: float,
    fill_prob: float = 0.7,
    slippage_bps: float = 5.0,
    fees_bps: float = 2.0,
) -> float:
    if not output or not isinstance(output, list) or not output[0]:
        return 0.0

    x = output[0]
    if not isinstance(x, dict):
        return 0.0

    profit_pct = float(x.get("profit_pct", 0.0)) / 100.0
    gross_ev = capital_usd * profit_pct

    friction = capital_usd * ((slippage_bps + fees_bps) / 10000.0)
    ev = fill_prob * (gross_ev - friction)

    denom = max(max_loss_usd, 1.0)
    score = ev / denom

    return score
