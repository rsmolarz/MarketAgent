"""
Geopolitical Dataset Loader for backtest-grade historical event data.

Converts raw GDELT/ACLED events into daily risk scores per region.
This makes GeopoliticalRiskAgent backtestable without relying on non-deterministic news feeds.

Sources:
- GDELT (Global Database of Events, Language, and Tone) - free, 1979-present
- ACLED (Armed Conflict Location & Event Data) - requires registration
"""
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/geopolitical")
DATA_DIR.mkdir(parents=True, exist_ok=True)

REGION_MAP = {
    "TAIWAN": ["TW", "TAIWAN", "TWN"],
    "UKRAINE": ["UA", "UKRAINE", "UKR", "RU", "RUSSIA", "RUS"],
    "MIDDLE_EAST": ["IL", "ISRAEL", "ISR", "PS", "PALESTINE", "GAZA", "IR", "IRAN", "IRN", "YE", "YEMEN", "YEM"],
    "SOUTH_CHINA_SEA": ["PH", "PHILIPPINES", "VN", "VIETNAM", "MY", "MALAYSIA"],
    "NORTH_KOREA": ["KP", "NORTH KOREA", "PRK"],
    "CHINA_US": ["CN", "CHINA", "CHN", "US", "USA"],
}

CONFLICT_EVENT_CODES = {
    19, 20, 21, 22, 23, 24, 25, 26,  # CAMEO conflict categories
    170, 171, 172, 173, 174, 175,    # Coerce
    180, 181, 182, 183,              # Assault
    190, 191, 192, 193, 194, 195,    # Fight
    200, 201, 202, 203, 204,         # Mass violence
}


def load_gdelt_events(csv_path: Path) -> pd.DataFrame:
    """
    Load GDELT event data from CSV/TSV file.
    
    GDELT files can be downloaded from:
    http://data.gdeltproject.org/events/index.html
    
    Expected columns: SQLDATE, Actor1Geo_CountryCode, Actor2Geo_CountryCode, 
                      EventCode, GoldsteinScale, NumMentions, AvgTone
    """
    try:
        df = pd.read_csv(csv_path, sep="\t", low_memory=False)
        df["date"] = pd.to_datetime(df["SQLDATE"].astype(str), format="%Y%m%d", errors="coerce")
        df = df.dropna(subset=["date"])
        logger.info(f"Loaded {len(df)} GDELT events from {csv_path}")
        return df
    except Exception as e:
        logger.error(f"Error loading GDELT data: {e}")
        return pd.DataFrame()


def classify_region(country_code: str) -> Optional[str]:
    """Map country code to tracked region."""
    if pd.isna(country_code):
        return None
    code = str(country_code).upper().strip()
    for region, codes in REGION_MAP.items():
        if code in codes:
            return region
    return None


def build_geopolitical_risk_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build daily risk index per region from GDELT events.
    
    Risk score formula:
    risk = min(100, conflict_events * 10 + severity_sum * 0.5 + mention_weight)
    """
    rows = []
    
    if df.empty:
        return pd.DataFrame(rows)
    
    df["region1"] = df.get("Actor1Geo_CountryCode", pd.Series()).apply(classify_region)
    df["region2"] = df.get("Actor2Geo_CountryCode", pd.Series()).apply(classify_region)
    
    for region in REGION_MAP.keys():
        region_df = df[(df["region1"] == region) | (df["region2"] == region)]
        
        if region_df.empty:
            continue
        
        grouped = region_df.groupby(region_df["date"].dt.date)
        
        for event_date, g in grouped:
            total = len(g)
            
            event_codes = g.get("EventCode", pd.Series())
            conflict = event_codes.isin(CONFLICT_EVENT_CODES).sum() if not event_codes.empty else 0
            
            goldstein = g.get("GoldsteinScale", pd.Series())
            severity = goldstein.abs().sum() if not goldstein.empty else 0
            
            mentions = g.get("NumMentions", pd.Series())
            mention_weight = mentions.sum() * 0.01 if not mentions.empty else 0
            
            risk = min(100, int(conflict * 10 + severity * 0.5 + mention_weight))
            
            rows.append({
                "date": pd.Timestamp(event_date),
                "region": region,
                "event_count": total,
                "conflict_events": int(conflict),
                "severity_score": float(severity),
                "risk_score": risk,
            })
    
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["date", "region"]).reset_index(drop=True)
    
    logger.info(f"Built risk index with {len(result)} region-day entries")
    return result


def save_risk_index(df: pd.DataFrame, filename: str = "geo_risk_index.parquet") -> Path:
    """Save risk index to parquet for fast loading."""
    out_path = DATA_DIR / filename
    df.to_parquet(out_path, index=False)
    logger.info(f"Saved risk index to {out_path}")
    return out_path


def load_risk_index(filename: str = "geo_risk_index.parquet") -> pd.DataFrame:
    """Load cached risk index."""
    path = DATA_DIR / filename
    if path.exists():
        df = pd.read_parquet(path)
        df["date"] = pd.to_datetime(df["date"])
        return df
    return pd.DataFrame()


def build_from_manual_events() -> pd.DataFrame:
    """
    Build risk index from manually curated events in geo_events.py.
    This is the fallback when GDELT data isn't available.
    """
    from backtests.geo_events import HISTORICAL_GEO_EVENTS
    
    rows = []
    for event in HISTORICAL_GEO_EVENTS:
        rows.append({
            "date": pd.Timestamp(event["date"]),
            "region": event["region"].upper().replace("-", "_"),
            "event_count": 1,
            "conflict_events": 1 if event["risk_score"] >= 70 else 0,
            "severity_score": event["risk_score"] / 10.0,
            "risk_score": event["risk_score"],
        })
    
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
    
    logger.info(f"Built risk index from {len(rows)} manual events")
    return df


def get_or_build_risk_index() -> pd.DataFrame:
    """
    Get cached risk index or build from available sources.
    Preference: cached parquet > GDELT files > manual events
    """
    cached = load_risk_index()
    if not cached.empty:
        return cached
    
    gdelt_files = list(DATA_DIR.glob("*.export.CSV")) + list(DATA_DIR.glob("*.csv"))
    if gdelt_files:
        all_events = pd.concat([load_gdelt_events(f) for f in gdelt_files], ignore_index=True)
        if not all_events.empty:
            index = build_geopolitical_risk_index(all_events)
            save_risk_index(index)
            return index
    
    manual_index = build_from_manual_events()
    save_risk_index(manual_index, "geo_risk_manual.parquet")
    return manual_index
