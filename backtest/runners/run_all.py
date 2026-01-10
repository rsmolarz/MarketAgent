from __future__ import annotations
from backtest.registry import load_manifest
from backtest.runners.run_one import run_one, DEFAULT_START, DEFAULT_END

CATEGORY_A = {
    "MarketCorrectionAgent",
    "EquityMomentumAgent",
    "BondStressAgent",
    "MacroWatcherAgent",
    "HeartbeatAgent",
    "GreatestTradeAgent",
    "CryptoStablecoinPremiumAgent",
}

def main(start: str = DEFAULT_START, end: str = DEFAULT_END):
    manifest = load_manifest()
    agents = [a["name"] for a in manifest["agents"] if a["name"] in CATEGORY_A]
    print("Running:", agents)

    for name in agents:
        try:
            run_one(name, start=start, end=end)
        except Exception as e:
            print(f"[FAIL] {name}: {e}")

if __name__ == "__main__":
    main()
