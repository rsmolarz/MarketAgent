def promotion_allowed(report: dict) -> tuple[bool, list[str]]:
    reasons = []
    fleet = report.get("fleet", {})
    agents = report.get("agents", {})

    if float(fleet.get("portfolio_pnl_bps", 0)) <= 0:
        reasons.append("Portfolio PnL <= 0")

    for name, a in agents.items():
        if a.get("decision") == "KILL":
            reasons.append(f"{name} marked KILL")
        if a.get("decision") == "PROMOTE":
            if float(a.get("pnl_sum_bps", 0)) < 150:
                reasons.append(f"{name} PROMOTE but pnl_sum_bps < 150")
            if float(a.get("error_rate", 0)) > 0:
                reasons.append(f"{name} PROMOTE but error_rate > 0")

    return (len(reasons) == 0), reasons
