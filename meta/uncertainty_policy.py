"""
Uncertainty → Cadence Modulation Policy

Maps LLM council uncertainty to agent execution frequency.
High uncertainty → slower execution (up to 3x interval)
Low uncertainty → normal baseline
"""


def cadence_multiplier(uncertainty: float) -> float:
    """
    Convert uncertainty ∈ [0,1] to interval multiplier.
    
    Returns:
        Multiplier for agent schedule interval:
        - 1.0: normal cadence
        - 1.5: slight slowdown
        - 2.0: moderate slowdown
        - 3.0: significant slowdown (very noisy agent)
    """
    if uncertainty >= 0.75:
        return 3.0
    if uncertainty >= 0.5:
        return 2.0
    if uncertainty >= 0.3:
        return 1.5
    return 1.0
