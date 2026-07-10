"""
Rule-based Risk Engine. Pure Python arithmetic — NO LLM calls, NO numeric
score ever comes from an AI model. This is what makes every score
defensible and reproducible.

Each function takes the raw metrics dict (from metrics_engine.compute_all_metrics)
plus AI Estimated inputs where a category genuinely has no deterministic
signal (e.g. Budget Risk, which needs Estimated Budget Risk from the LLM
layer because there's no `actual_spend` column in the source database).
"""

from typing import Optional
from app.schemas.report_schema import RiskCategory
from app.core.config import get_risk_weights


def _severity_from_score(score: float) -> str:
    thresholds = {"critical": 80, "high": 60, "medium": 35}
    if score >= thresholds["critical"]:
        return "Critical"
    if score >= thresholds["high"]:
        return "High"
    if score >= thresholds["medium"]:
        return "Medium"
    return "Low"


def calculate_timeline_risk(raw: dict) -> RiskCategory:
    days_remaining = raw.get("days_remaining")
    overdue = raw.get("overdue_milestones_count", 0)
    total_milestones = raw.get("total_milestones", 0) or 1

    if days_remaining is None:
        # No timeline data at all — low confidence, mid score as a neutral default.
        return RiskCategory(
            name="Timeline Risk", score=50.0, severity="Medium", source="calculated",
            confidence=0.3, reason="No timeline data available for this project.",
            used_metrics=[],
        )

    urgency = max(0.0, 100 - days_remaining * 2) if days_remaining >= 0 else 100.0
    overdue_penalty = (overdue / total_milestones) * 40
    score = min(100.0, urgency * 0.6 + overdue_penalty)

    return RiskCategory(
        name="Timeline Risk", score=round(score, 1), severity=_severity_from_score(score),
        source="calculated", confidence=0.9,
        reason=f"{days_remaining} days remaining with {overdue} overdue milestone(s).",
        used_metrics=["Days Remaining", "Overdue Milestones"],
    )


def calculate_resource_risk(raw: dict) -> RiskCategory:
    avg_ratio = raw.get("avg_workload_ratio")
    overloaded = raw.get("overloaded_members_count", 0)
    team_size = raw.get("team_size", 0) or 1

    if avg_ratio is None:
        return RiskCategory(
            name="Resource Risk", score=50.0, severity="Medium", source="calculated",
            confidence=0.3, reason="No workload data available.", used_metrics=[],
        )

    ratio_component = min(100.0, avg_ratio * 50)
    overload_component = (overloaded / team_size) * 50
    score = min(100.0, ratio_component * 0.5 + overload_component * 0.5)

    return RiskCategory(
        name="Resource Risk", score=round(score, 1), severity=_severity_from_score(score),
        source="calculated", confidence=0.85,
        reason=f"Average workload ratio {avg_ratio}, {overloaded}/{team_size} member(s) overloaded.",
        used_metrics=["Average Workload Ratio", "Overloaded Members"],
    )


def calculate_productivity_risk(raw: dict) -> RiskCategory:
    progress_pct = raw.get("progress_pct")
    avg_age = raw.get("avg_task_age_days")
    velocity = raw.get("velocity_last_period", 0)

    if progress_pct is None:
        return RiskCategory(
            name="Productivity Risk", score=50.0, severity="Medium", source="calculated",
            confidence=0.3, reason="No task data available.", used_metrics=[],
        )

    stagnation = min(100.0, (avg_age or 0) * 3)
    low_velocity_penalty = 30.0 if velocity == 0 else max(0.0, 15 - velocity)
    score = min(100.0, stagnation * 0.5 + low_velocity_penalty * 0.5 + (100 - progress_pct) * 0.2)
    score = min(100.0, score)

    return RiskCategory(
        name="Productivity Risk", score=round(score, 1), severity=_severity_from_score(score),
        source="calculated", confidence=0.8,
        reason=f"Progress {progress_pct}%, average open task age {avg_age} days, velocity {velocity}.",
        used_metrics=["Project Progress", "Average Open Task Age", "Velocity"],
    )


def calculate_dependency_risk(raw: dict, total_tasks: int) -> RiskCategory:
    blocked = raw.get("blocked_tasks_count", 0)
    total_tasks = total_tasks or 1
    score = min(100.0, (blocked / total_tasks) * 150)

    return RiskCategory(
        name="Dependency Risk", score=round(score, 1), severity=_severity_from_score(score),
        source="calculated", confidence=0.9,
        reason=f"{blocked} task(s) blocked by incomplete dependencies.",
        used_metrics=["Blocked Tasks"],
    )


def calculate_communication_risk(raw: dict, project_priority: Optional[str]) -> RiskCategory:
    meeting_count = raw.get("meeting_count", 0)
    is_high_priority = (project_priority or "").lower() in ("high", "critical")

    base = max(0.0, 60 - meeting_count * 20)
    score = min(100.0, base * (1.3 if is_high_priority else 1.0))

    return RiskCategory(
        name="Communication Risk", score=round(score, 1), severity=_severity_from_score(score),
        source="calculated", confidence=0.6,  # weaker signal, meeting count is an indirect proxy
        reason=f"{meeting_count} recent meeting(s) for a '{project_priority or 'unset'}' priority project.",
        used_metrics=["Recent Meeting Count"],
    )


def calculate_confirmed_risk_component(raw: dict) -> RiskCategory:
    """
    Folds the manually-logged Risks table directly into the score set —
    this is ground truth from the PM, not inferred, so confidence is high.
    """
    load = raw.get("confirmed_risk_load", 0)
    score = min(100.0, load * 12)

    return RiskCategory(
        name="Confirmed Risk (Manual)", score=round(score, 1), severity=_severity_from_score(score),
        source="calculated", confidence=0.95,
        reason=f"{len(raw.get('open_confirmed_risks', []))} open manually-logged risk(s).",
        used_metrics=["Open Confirmed Risks"],
    )
