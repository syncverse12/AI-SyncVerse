"""Deterministic aggregation of the manually-logged Risks table.
This is ground truth from the PM, not inferred - it's folded into the
Overall Risk Score as its own weighted component."""

from typing import List
from app.schemas.context_schema import ConfirmedRiskItem, RiskSeverity

_SEVERITY_POINTS = {
    RiskSeverity.low: 10,
    RiskSeverity.medium: 30,
    RiskSeverity.high: 60,
    RiskSeverity.critical: 90,
}


def confirmed_risk_load(risks: List[ConfirmedRiskItem]) -> dict:
    open_risks = [r for r in risks if (r.status or "").lower() not in {"closed", "resolved"}]
    if not open_risks:
        return {"score": 0, "open_count": 0, "by_severity": {}}

    score = min(100, sum(_SEVERITY_POINTS[r.severity] for r in open_risks) / len(open_risks))
    by_severity: dict = {}
    for r in open_risks:
        by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1

    return {"score": round(score, 1), "open_count": len(open_risks), "by_severity": by_severity}
