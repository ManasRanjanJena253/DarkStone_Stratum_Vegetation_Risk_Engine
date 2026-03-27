import numpy as np
from typing import Optional, List
from .risk import compute_risk_score, label_risk


def build_embedding(
    ndvi: Optional[float],
    risk_score: Optional[float],
    tree_height: Optional[float],
    clearance: Optional[float],
    species_enc: int = 0,
) -> List[float]:
    vec = [
        ndvi if ndvi is not None else 0.0,
        risk_score if risk_score is not None else 0.0,
        tree_height if tree_height is not None else 0.0,
        clearance if clearance is not None else 0.0,
        float(species_enc),
    ]
    arr = np.array(vec, dtype=float)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def fuse_analysis_result(
    tree_height: Optional[float],
    wire_height: Optional[float],
    ndvi: Optional[float],
    growth_rate: float = 0.5,
    species: Optional[str] = None,
) -> dict:
    from .lidar_ops import compute_clearance
    clearance = compute_clearance(wire_height, tree_height)
    risk_score = compute_risk_score(clearance, ndvi, growth_rate)
    risk_label = label_risk(risk_score)
    embedding = build_embedding(ndvi, risk_score, tree_height, clearance)
    return {
        "clearance_m": clearance,
        "risk_score": risk_score,
        "risk_label": risk_label,
        "embedding": embedding,
    }