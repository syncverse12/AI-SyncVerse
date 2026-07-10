from app.metrics.dependency_metrics import compute_dependency_and_confirmed_risk_metrics
from app.schemas.context_schema import ProjectContext, ProjectInfo, TaskItem, ConfirmedRiskItem


def _context(tasks=None, risks=None):
    return ProjectContext(
        project=ProjectInfo(project_id="p1", project_name="Test"),
        tasks=tasks or [], confirmed_risks=risks or [],
        collection_mode="unified",
    )


def test_blocked_task_detected_when_dependency_not_done():
    tasks = [
        TaskItem(task_id="t1", title="A", status="done"),
        TaskItem(task_id="t2", title="B", status="todo", depends_on_task_ids=["t3"]),
        TaskItem(task_id="t3", title="C", status="todo"),
    ]
    context = _context(tasks=tasks)
    result = compute_dependency_and_confirmed_risk_metrics(context)
    assert result["blocked_tasks_count"] == 1  # only t2 depends on an unfinished task


def test_confirmed_risk_load_weighted_by_severity():
    risks = [
        ConfirmedRiskItem(risk_id="r1", risk_name="A", severity="critical", status="open"),
        ConfirmedRiskItem(risk_id="r2", risk_name="B", severity="low", status="open"),
        ConfirmedRiskItem(risk_id="r3", risk_name="C", severity="high", status="closed"),
    ]
    context = _context(risks=risks)
    result = compute_dependency_and_confirmed_risk_metrics(context)
    assert len(result["open_confirmed_risks"]) == 2  # r3 excluded (closed)
    assert result["confirmed_risk_load"] == 4 + 1  # critical(4) + low(1)
