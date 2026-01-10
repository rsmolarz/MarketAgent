import os

def drawdown_breach(fleet: dict) -> bool:
    thresh = float(os.environ.get("MAX_DRAWDOWN_BPS", "250"))
    dd = float(fleet.get("portfolio_max_drawdown_bps", 0) or 0)
    return dd >= thresh
