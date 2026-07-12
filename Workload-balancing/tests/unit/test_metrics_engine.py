from app.context.builder import ContextBuilder
from app.engine.metrics_engine import MetricsEngine
from app.models.raw import RawEmployee, RawTask, RawTeamSnapshot


def _ctx():
    snapshot = RawTeamSnapshot(
        scope_type="project", scope_id="p1", scope_name="Test",
        employees=[
            RawEmployee(id="e1", first_name="A", last_name="B", availability_status="Busy"),
            RawEmployee(id="e2", first_name="C", last_name="D", availability_status="Available"),
        ],
        tasks=[
            RawTask(id="t1", title="x", status="in_progress", priority=5, assigned_to_user_id="e1",
                    due_date="2020-01-01T00:00:00"),
            RawTask(id="t2", title="y", status="todo", priority=3, assigned_to_user_id="e2"),
        ],
    )
    return ContextBuilder().build(snapshot, source="demo")


def test_metrics_engine_computes_expected_keys():
    metrics = MetricsEngine().compute(_ctx())
    assert metrics["employee_count"] == 2
    assert metrics["task_count"] == 2
    assert "team_capacity_utilization_pct" in metrics
    assert 0.0 <= metrics["overdue_task_ratio"] <= 1.0


def test_metrics_engine_handles_empty_context():
    from app.models.context import WorkloadContext
    empty = WorkloadContext(scope_type="project", scope_id="p1", source="demo", employees=[], tasks=[])
    metrics = MetricsEngine().compute(empty)
    assert metrics == {"employee_count": 0}
