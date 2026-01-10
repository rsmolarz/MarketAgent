def promotion_decision(stats, *,
                       min_runs=200,
                       min_cap_reward_mean=0.10,
                       min_sharpe=0.20,
                       max_drawdown=-2.0):
    """
    Determine if an agent should be promoted based on capital-weighted metrics.
    
    stats example:
    {
      "count": 500,
      "avg_reward": 0.12,
      "cap_reward_mean": 0.15,
      "sharpe": 0.35,
      "drawdown": -1.1
    }
    
    Returns:
        tuple: (should_promote: bool, reason: str)
    """
    if stats.get("count", 0) < min_runs:
        return False, "insufficient_runs"

    if stats.get("cap_reward_mean", stats.get("avg_reward", 0.0)) < min_cap_reward_mean:
        return False, "cap_reward_mean_below_threshold"

    if stats.get("sharpe", 0.0) < min_sharpe:
        return False, "sharpe_below_threshold"

    if stats.get("drawdown", 0.0) <= max_drawdown:
        return False, "drawdown_too_deep"

    return True, "promote"


def get_promotion_report(stats, **kwargs):
    """
    Generate a detailed promotion report for an agent.
    
    Returns:
        dict: Report with decision, reason, and threshold comparisons
    """
    defaults = {
        "min_runs": 200,
        "min_cap_reward_mean": 0.10,
        "min_sharpe": 0.20,
        "max_drawdown": -2.0
    }
    defaults.update(kwargs)
    
    decision, reason = promotion_decision(stats, **defaults)
    
    return {
        "decision": "promote" if decision else "hold",
        "reason": reason,
        "stats": stats,
        "thresholds": defaults,
        "checks": {
            "runs": {
                "value": stats.get("count", 0),
                "threshold": defaults["min_runs"],
                "passed": stats.get("count", 0) >= defaults["min_runs"]
            },
            "cap_reward_mean": {
                "value": stats.get("cap_reward_mean", stats.get("avg_reward", 0.0)),
                "threshold": defaults["min_cap_reward_mean"],
                "passed": stats.get("cap_reward_mean", stats.get("avg_reward", 0.0)) >= defaults["min_cap_reward_mean"]
            },
            "sharpe": {
                "value": stats.get("sharpe", 0.0),
                "threshold": defaults["min_sharpe"],
                "passed": stats.get("sharpe", 0.0) >= defaults["min_sharpe"]
            },
            "drawdown": {
                "value": stats.get("drawdown", 0.0),
                "threshold": defaults["max_drawdown"],
                "passed": stats.get("drawdown", 0.0) > defaults["max_drawdown"]
            }
        }
    }
