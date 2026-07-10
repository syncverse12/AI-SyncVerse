from datetime import datetime, timedelta, timezone
from app.metrics.timeline_metrics import compute_timeline_metrics
from app.schemas.context_schema import ProjectContext, ProjectInfo, TimelineItem, MilestoneItem

NOW = datetime.now(timezone.utc)


def _context(timeline=None, milestones=None):
    return ProjectContext(
        project=ProjectInfo(project_id="p1", project_name="Test"),
        timeline=timeline or [],
        milestones=milestones or [],
        collection_mode="unified",
    )


def test_days_remaining_computed_from_nearest_due_date():
    context = _context(timeline=[TimelineItem(timeline_id="t1", due_date=NOW + timedelta(days=10))])
    result = compute_timeline_metrics(context)
    assert result["days_remaining"] == 9 or result["days_remaining"] == 10  # allow for exec-time rounding


def test_overdue_milestones_counted_correctly():
    milestones = [
        MilestoneItem(milestone_id="m1", name="A", target_date=NOW - timedelta(days=2), status="pending"),
        MilestoneItem(milestone_id="m2", name="B", target_date=NOW + timedelta(days=5), status="pending"),
        MilestoneItem(milestone_id="m3", name="C", target_date=NOW - timedelta(days=1), status="done"),
    ]
    context = _context(milestones=milestones)
    result = compute_timeline_metrics(context)
    assert result["overdue_milestones_count"] == 1  # only m1: overdue AND not done


def test_no_timeline_data_returns_none_days_remaining():
    context = _context()
    result = compute_timeline_metrics(context)
    assert result["days_remaining"] is None
