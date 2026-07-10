from app.metrics.workload_metrics import compute_workload_metrics
from app.schemas.context_schema import ProjectContext, ProjectInfo, TaskItem, TeamMemberItem


def _context(tasks=None, members=None):
    return ProjectContext(
        project=ProjectInfo(project_id="p1", project_name="Test"),
        tasks=tasks or [],
        team_members=members or [],
        collection_mode="unified",
    )


def test_overloaded_member_flagged_when_ratio_exceeds_threshold():
    tasks = [TaskItem(task_id=str(i), title=f"t{i}", status="todo", assigned_user_id="u1") for i in range(5)]
    members = [TeamMemberItem(user_id="u1", task_capacity=2)]
    context = _context(tasks=tasks, members=members)
    result = compute_workload_metrics(context)
    assert result["overloaded_members_count"] == 1


def test_no_members_returns_none_avg_ratio():
    context = _context()
    result = compute_workload_metrics(context)
    assert result["avg_workload_ratio"] is None
    assert result["team_size"] == 0
