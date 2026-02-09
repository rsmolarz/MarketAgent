import json
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/api_toggles.json")

DEFAULT_TOGGLES = {
    "openai": {"label": "OpenAI (GPT)", "enabled": True, "category": "LLM", "description": "GPT models for builder agent, council, analysis"},
    "anthropic": {"label": "Anthropic (Claude)", "enabled": True, "category": "LLM", "description": "Claude models for AI analysis, council, thesis compression"},
    "gemini": {"label": "Google Gemini", "enabled": True, "category": "LLM", "description": "Gemini models for LLM council ensemble"},
    "news_api": {"label": "NewsAPI", "enabled": True, "category": "Data", "description": "News headlines for geopolitical risk agent"},
    "alpha_vantage": {"label": "Alpha Vantage", "enabled": True, "category": "Data", "description": "Market data for financial analysis"},
    "coinbase": {"label": "Coinbase", "enabled": True, "category": "Data", "description": "Cryptocurrency prices and trading data"},
    "etherscan": {"label": "Etherscan", "enabled": True, "category": "Data", "description": "Ethereum blockchain data for whale tracking"},
    "sendgrid": {"label": "SendGrid", "enabled": True, "category": "Email", "description": "Email notifications and daily summaries"},
    "yahoo_finance": {"label": "Yahoo Finance", "enabled": True, "category": "Data", "description": "Stock prices, indices, bonds via yfinance"},
    "crm_webhook": {"label": "CRM Webhooks", "enabled": True, "category": "Integration", "description": "External CRM handoff and deal room sync"},
}

_lock = Lock()


def _ensure_config():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_TOGGLES, indent=2))


def load_toggles():
    _ensure_config()
    try:
        raw = CONFIG_PATH.read_text().strip()
        if not raw:
            raise ValueError("Empty config file")
        data = json.loads(raw)
        for key, default in DEFAULT_TOGGLES.items():
            if key not in data:
                data[key] = default
        return data
    except (json.JSONDecodeError, IOError, ValueError) as e:
        logger.warning(f"API toggle config unreadable ({e}), failing closed (all disabled)")
        closed = {}
        for key, default in DEFAULT_TOGGLES.items():
            closed[key] = {**default, "enabled": False}
        return closed


def save_toggles(data):
    with _lock:
        _ensure_config()
        CONFIG_PATH.write_text(json.dumps(data, indent=2))


def is_api_enabled(api_name: str) -> bool:
    toggles = load_toggles()
    entry = toggles.get(api_name)
    if entry is None:
        return True
    return entry.get("enabled", True)


def set_api_enabled(api_name: str, enabled: bool):
    toggles = load_toggles()
    if api_name in toggles:
        toggles[api_name]["enabled"] = enabled
        save_toggles(toggles)
        logger.info(f"API toggle: {api_name} set to {'enabled' if enabled else 'disabled'}")
        return True
    return False


def set_all_apis(enabled: bool):
    toggles = load_toggles()
    for key in toggles:
        toggles[key]["enabled"] = enabled
    save_toggles(toggles)
    logger.info(f"All APIs set to {'enabled' if enabled else 'disabled'}")


def api_guard(api_name: str, action_description: str = ""):
    if not is_api_enabled(api_name):
        desc = f" ({action_description})" if action_description else ""
        msg = f"API '{api_name}' is disabled via admin toggle{desc}. Skipping."
        logger.info(msg)
        return False
    return True
