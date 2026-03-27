from typing import Optional
from ..core.config import settings


RISK_WEIGHTS = {
    "clearance": 0.5,
    "ndvi": 0.3,
    "growth_rate": 0.2,
}


def compute_risk_score(
    clearance_m: Optional[float],
    ndvi: Optional[float],
    growth_rate_m_yr: float = 0.5,
) -> float:
    score = 0.0

    if clearance_m is not None:
        threshold = settings.risk_threshold_meters
        if clearance_m <= 0:
            clearance_score = 1.0
        elif clearance_m >= threshold * 2:
            clearance_score = 0.0
        else:
            clearance_score = 1.0 - (clearance_m / (threshold * 2))
        score += RISK_WEIGHTS["clearance"] * clearance_score

    if ndvi is not None:
        ndvi_clamped = max(0.0, min(1.0, ndvi))
        score += RISK_WEIGHTS["ndvi"] * ndvi_clamped

    growth_score = min(1.0, growth_rate_m_yr / 1.5)
    score += RISK_WEIGHTS["growth_rate"] * growth_score

    return round(min(1.0, max(0.0, score)), 4)


def label_risk(score: float) -> str:
    if score >= 0.7:
        return "Critical"
    elif score >= 0.45:
        return "High"
    elif score >= 0.2:
        return "Medium"
    return "Low"