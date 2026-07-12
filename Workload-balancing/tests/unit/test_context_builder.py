from app.context.builder import ContextBuilder
from app.models.raw import RawEmployee, RawTask, RawTeamSnapshot, RawTimeLog


def _snapshot():
    employees = [
        RawEmployee(id="e1", first_name="Ahmed", last_name="Nasser",
                    skills_raw='["python","backend"]', availability_status="Busy"),
        RawEmployee(id="e2", first_name="Sara", last_name="Ali",
                    skills_raw="frontend, react", availability_status="Available"),
    ]
    tasks = [
        RawTask(id="t1", title="Fix bug", status="in_progress", priority=9,
                assigned_to_user_id="e1", due_date="2020-01-01T00:00:00"),
        RawTask(id="t2", title="Write docs", status="todo", priority=2, assigned_to_user_id="e2"),
    ]
    logs = [RawTimeLog(id="l1", task_id="t1", user_id="e1",
                        start_time="2026-01-01T00:00:00", duration_minutes=120)]
    return RawTeamSnapshot(scope_type="project", scope_id="p1", scope_name="Test",
                            employees=employees, tasks=tasks, time_logs=logs)


def test_build_produces_one_employee_per_raw_employee():
    ctx = ContextBuilder().build(_snapshot(), source="demo")
    assert len(ctx.employees) == 2
    assert ctx.source == "demo"


def test_overdue_task_marks_delayed():
    ctx = ContextBuilder().build(_snapshot(), source="demo")
    ahmed = next(e for e in ctx.employees if e.name == "Ahmed Nasser")
    assert ahmed.delayed_tasks == 1
    assert ahmed.active_tasks == 1


def test_skills_parsed_from_json_and_csv():
    ctx = ContextBuilder().build(_snapshot(), source="demo")
    ahmed = next(e for e in ctx.employees if e.name == "Ahmed Nasser")
    sara = next(e for e in ctx.employees if e.name == "Sara Ali")
    assert ahmed.skills == ["python", "backend"]
    assert sara.skills == ["frontend", "react"]


def test_high_priority_task_seeds_critical_complexity():
    ctx = ContextBuilder().build(_snapshot(), source="demo")
    ahmed = next(e for e in ctx.employees if e.name == "Ahmed Nasser")
    assert ahmed.task_complexity_distribution.critical == 1


def test_empty_snapshot_produces_warning():
    empty = RawTeamSnapshot(scope_type="project", scope_id="p2", scope_name="Empty")
    ctx = ContextBuilder().build(empty, source="demo")
    assert ctx.employees == []
    assert any("No employees" in w for w in ctx.data_quality_warnings)
