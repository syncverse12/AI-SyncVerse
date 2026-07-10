"""
Combines every RiskCategory (including the AI-Estimated Budget Risk, which
arrives as a RiskCategory too — see ai_estimators/estimated_metrics.py)
into a single Overall Risk score using the configurable weights from
config/risk_rules.yaml.

Still zero LLM involvement: the LLM only ever produced the *inputs*
(Estimated Budget Risk's score is itself computed by a deterministic
formula inside ai_estimators, using AI-estimated *metrics* as inputs —
see that module for the boundary).
"""

from typing import List
from app.schemas.report_schema import RiskCategory, OverallRisk
from app.core.config import get_risk_weights


def _severity_from_score(score: float) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


CATEGORY_TO_WEIGHT_KEY = {
    "Timeline Risk": "timeline",
    "Resource Risk": "resource",
    "Productivity Risk": "productivity",
    "Communication Risk": "communication",
    "Budget Risk": "budget",
}


def aggregate_overall_risk(categories: List[RiskCategory]) -> OverallRisk:
    weights = get_risk_weights()
    total_weight = 0.0
    weighted_sum = 0.0
    confidence_sum = 0.0
    weighted_categories = 0

    for cat in categories:
        weight_key = CATEGORY_TO_WEIGHT_KEY.get(cat.name)
        if weight_key is None:
            continue  # e.g. Dependency Risk / Confirmed Risk feed severity but not the weighted average
        weight = weights.get(weight_key, 0.0)
        weighted_sum += cat.score * weight
        total_weight += weight
        confidence_sum += cat.confidence
        weighted_categories += 1

    if total_weight == 0:
        overall_score = sum(c.score for c in categories) / max(len(categories), 1)
    else:
        overall_score = weighted_sum / total_weight

    # Dependency + Confirmed risks act as a floor: severe blockers or many
    # open manual risks should never be fully diluted by a healthy timeline.
    boosters = [c for c in categories if c.name in ("Dependency Risk", "Confirmed Risk (Manual)")]
    if boosters:
        max_booster = max(b.score for b in boosters)
        overall_score = max(overall_score, overall_score * 0.7 + max_booster * 0.3)

    overall_score = round(min(overall_score, 100.0), 1)
    overall_confidence = round(confidence_sum / weighted_categories, 2) if weighted_categories else 0.5

    return OverallRisk(
        score=overall_score,
        level=_severity_from_score(overall_score),
        confidence=overall_confidence,
    )
