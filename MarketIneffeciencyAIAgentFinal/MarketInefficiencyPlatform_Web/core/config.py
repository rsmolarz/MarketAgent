from pathlib import Path
import yaml

DEFAULT_CONFIG = {
    "agents": {"enabled": ["SpreadScannerAgent","MomentumVolumeAgent","PortfolioRiskAgent"],
               "settings": {"paper_mode": True}},
    "data_sources": {"crypto": {"enabled": False}, "equities": {"enabled": False}},
    "thresholds": {"risk_thresholds": {}},
    "logging": {"level": "DEBUG"},
    "alerts": {"email_to": "", "whatsapp_to": ""},
}

def load_config(config_path: str | Path) -> dict:
    p = Path(config_path)
    if not p.exists():
        return DEFAULT_CONFIG
    with p.open("r") as f:
        data = yaml.safe_load(f) or {}
    # Merge shallow with defaults
    cfg = DEFAULT_CONFIG.copy()
    for k, v in (data or {}).items():
        cfg[k] = v
    return cfg
