def extract_features(spy_df, vix_df, rates_df, commodities_df=None):
    spy_close_now = float(spy_df["Close"].iloc[-1])
    spy_close_20d = float(spy_df["Close"].iloc[-20])
    spy_return_20d = spy_close_now / spy_close_20d - 1
    
    vix_level = float(vix_df["Close"].iloc[-1])
    
    rates_now = float(rates_df["Close"].iloc[-1])
    rates_20d = float(rates_df["Close"].iloc[-20])
    rates_change = rates_now - rates_20d

    features = {
        "spy_trend": "up" if spy_return_20d > 0 else "down",
        "volatility": "high" if vix_level > 25 else "low",
        "rates_trend": "up" if rates_change > 0.1 else "down_or_flat"
    }

    if commodities_df is not None and len(commodities_df) >= 20:
        comm_now = float(commodities_df["Close"].iloc[-1])
        comm_20d = float(commodities_df["Close"].iloc[-20])
        comm_return = comm_now / comm_20d - 1
        features["commodities"] = "up" if comm_return > 0 else "down"

    return features
