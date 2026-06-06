from __future__ import annotations


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def signed_clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


def qualitative_to_multiplier(effect: float, baseline: float = 1.0, scale: float = 0.6) -> float:
    return clamp(baseline + effect * scale, 0.0, 2.0)
