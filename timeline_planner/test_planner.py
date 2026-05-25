"""
tests/test_planner.py
---------------------
Integration tests covering the full planning pipeline.
Run with:  python -m pytest tests/ -v
or simply: python tests/test_planner.py
"""

from __future__ import annotations

import sys
import os
import traceback
from datetime import date, timedelta
from typing import List

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from planner import (
    DependencyGraph,
    EventType,
    ProjectPlanner,
    ReplanningEngine,
    ReplanningEvent,
    Resource,
    SprintGenerator,
    Task,
    TaskPriority,
    TaskStatus,
    estimate_task_duration,
    fill_missing_estimates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_resources() -> List[Resource]:
    return [
        Resource(
            name="Alice",
            capacity=1.0,
            skills=["backend", "python", "api"],
            available_from=date.today(),
        ),
        Resource(
            name="Bob",
            capacity=0.8,
            skills=["frontend", "react", "css"],
            available_from=date.today(),
        ),
        Resource(
            name="Carol",
            capacity=1.0,
            skills=["devops", "docker", "ci"],
            available_from=date.today(),
        ),
    ]


def make_tasks() -> List[Task]:
    t1 = Task(
        name="Design system architecture",
        priority=TaskPriority.HIGH,
        required_skills=["backend"],
        estimated_hours=16.0,
    )
    t2 = Task(
        name="Set up CI/CD pipeline",
        priority=TaskPriority.HIGH,
        required_skills=["devops"],
        estimated_hours=8.0,
    )
    t3 = Task(
        name="Implement REST API",
        priority=TaskPriority.HIGH,
        required_skills=["backend", "python"],
        estimated_hours=40.0,
        dependencies=[t1.id],
    )
    t4 = Task(
        name="Build frontend dashboard",
        priority=TaskPriority.MEDIUM,
        required_skills=["frontend", "react"],
        estimated_hours=32.0,
        dependencies=[t3.id],
    )
    t5 = Task(
        name="Write API documentation",
        priority=TaskPriority.LOW,
        required_skills=["backend"],
        estimated_hours=8.0,
        dependencies=[t3.id],
    )
    t6 = Task(
        name="Deploy to production",
        priority=TaskPriority.CRITICAL,
        required_skills=["devops"],
        estimated_hours=4.0,
        dependencies=[t4.id, t5.id, t2.id],
    )
    return [t1, t2, t3, t4, t5, t6]


# ---------------------------------------------------------------------------
# Test runner (no pytest required)
# ---------------------------------------------------------------------------

PASS = "✓"
FAIL = "✗"
results = []


def run_test(name: str, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"  {PASS}  {name}")
    except Exception as exc:
        results.append((FAIL, name))
        print(f"  {FAIL}  {name}")
        traceback.print_exc()


# ===========================================================================
# 1. Duration Estimation
# ===========================================================================

def test_estimate_milestone():
    t = Task(name="Project kickoff", is_milestone=True)
    assert estimate_task_duration(t) == 0.0


def test_estimate_keyword_match():
    t = Task(name="Implement REST API backend", priority=TaskPriority.HIGH)
    hours = estimate_task_duration(t)
    assert hours > 0, "Estimated hours must be positive"


def test_fill_missing():
    tasks = [
        Task(name="Design blueprint", estimated_hours=None),
        Task(name="Write code",        estimated_hours=20.0),
    ]
    fill_missing_estimates(tasks)
    assert tasks[0].estimated_hours is not None and tasks[0].estimated_hours > 0
    assert tasks[1].estimated_hours == 20.0, "Existing estimate must not change"


# ===========================================================================
# 2. Dependency Graph
# ===========================================================================

def test_dag_builds_correctly():
    tasks = make_tasks()
    g = DependencyGraph(tasks)
    assert len(g.topological_order()) == len(tasks)


def test_dag_detects_cycle():
    t1 = Task(name="A", estimated_hours=4.0)
    t2 = Task(name="B", estimated_hours=4.0, dependencies=[t1.id])
    t1.dependencies = [t2.id]   # introduce cycle
    try:
        DependencyGraph([t1, t2])
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Cycle" in str(e)


def test_dag_roots_and_leaves():
    tasks = make_tasks()
    g = DependencyGraph(tasks)
    roots = g.roots()
    leaves = g.leaves()
    assert len(roots) > 0
    assert len(leaves) > 0


def test_cpm_produces_critical_path():
    tasks = make_tasks()
    g = DependencyGraph(tasks)
    nodes, cp = g.compute_cpm()
    assert len(cp) > 0, "Critical path must not be empty"
    # Critical nodes must have zero float
    for tid in cp:
        assert nodes[tid].is_critical, f"Task {tid} on CP must have zero float"


def test_cpm_forward_backward():
    tasks = make_tasks()
    g = DependencyGraph(tasks)
    nodes, _ = g.compute_cpm()
    for tid, node in nodes.items():
        assert node.ef >= node.es, "EF must be >= ES"
        assert node.lf >= node.ls, "LF must be >= LS"
        assert node.ls >= node.es - 1e-6, "LS must be >= ES (total float >= 0)"


# ===========================================================================
# 3. Full Initial Plan
# ===========================================================================

def test_build_initial_plan():
    tasks = make_tasks()
    resources = make_resources()
    planner = ProjectPlanner(
        project_name="Test Project",
        deadline=date.today() + timedelta(days=90),
        tasks=tasks,
        resources=resources,
        project_start=date.today(),
    )
    plan = planner.build_initial_plan()
    assert plan is not None
    assert len(plan.tasks) == len(tasks)
    assert len(plan.sprints) > 0
    assert len(plan.critical_path) > 0


def test_all_tasks_scheduled():
    tasks = make_tasks()
    resources = make_resources()
    planner = ProjectPlanner(
        project_name="Test Project",
        deadline=date.today() + timedelta(days=90),
        tasks=tasks,
        resources=resources,
    )
    plan = planner.build_initial_plan()
    for task in plan.tasks:
        assert task.start_date is not None, f"Task '{task.name}' has no start_date"
        assert task.end_date   is not None, f"Task '{task.name}' has no end_date"
        assert task.end_date   >= task.start_date


def test_dependency_ordering_respected():
    """Every task must start after all its dependencies finish."""
    tasks = make_tasks()
    resources = make_resources()
    planner = ProjectPlanner(
        project_name="Order Test",
        deadline=date.today() + timedelta(days=120),
        tasks=tasks,
        resources=resources,
    )
    plan = planner.build_initial_plan()
    task_map = {t.id: t for t in plan.tasks}
    for task in plan.tasks:
        for dep_id in task.dependencies:
            dep = task_map.get(dep_id)
            if dep and dep.end_date and task.start_date:
                assert task.start_date >= dep.end_date, (
                    f"Task '{task.name}' starts before dep '{dep.name}' finishes"
                )


def test_resources_assigned():
    tasks = make_tasks()
    resources = make_resources()
    planner = ProjectPlanner(
        project_name="Resource Test",
        deadline=date.today() + timedelta(days=120),
        tasks=tasks,
        resources=resources,
    )
    plan = planner.build_initial_plan()
    resource_ids = {r.id for r in resources}
    for task in plan.tasks:
        if not task.is_milestone:
            assert task.assigned_to in resource_ids, (
                f"Task '{task.name}' assigned to unknown resource '{task.assigned_to}'"
            )


def test_sprint_task_coverage():
    """Every non-completed task must appear in exactly one sprint."""
    tasks = make_tasks()
    resources = make_resources()
    planner = ProjectPlanner(
        project_name="Sprint Test",
        deadline=date.today() + timedelta(days=120),
        tasks=tasks,
        resources=resources,
    )
    plan = planner.build_initial_plan()
    sprint_tasks = {tid for s in plan.sprints for tid in s.task_ids}
    for task in plan.tasks:
        if not task.is_complete:
            assert task.id in sprint_tasks, (
                f"Task '{task.name}' not found in any sprint"
            )


def test_plan_serialises_to_dict():
    tasks = make_tasks()
    resources = make_resources()
    planner = ProjectPlanner(
        project_name="Serial Test",
        deadline=date.today() + timedelta(days=90),
        tasks=tasks,
        resources=resources,
    )
    plan = planner.build_initial_plan()
    d = plan.to_dict()
    assert "tasks" in d
    assert "sprints" in d
    assert "critical_path" in d
    assert "is_on_time" in d


# ===========================================================================
# 4. Replanning
# ===========================================================================

def _base_planner() -> ProjectPlanner:
    tasks = make_tasks()
    resources = make_resources()
    planner = ProjectPlanner(
        project_name="Replan Test",
        deadline=date.today() + timedelta(days=120),
        tasks=tasks,
        resources=resources,
    )
    planner.build_initial_plan()
    return planner


def test_replan_task_completed_late():
    planner = _base_planner()
    first_task = planner.current_plan.tasks[0]
    original_hours = first_task.estimated_hours or 8.0

    event = ReplanningEvent(
        event_type=EventType.TASK_COMPLETED_LATE,
        task_id=first_task.id,
        new_value=original_hours * 2,   # took twice as long
    )
    updated = planner.recalculate_plan(event)
    updated_task = updated.get_task(first_task.id)
    assert updated_task.status == TaskStatus.COMPLETED
    assert updated_task.actual_hours == original_hours * 2


def test_replan_task_completed_early():
    planner = _base_planner()
    first_task = planner.current_plan.tasks[0]
    original_hours = first_task.estimated_hours or 16.0

    event = ReplanningEvent(
        event_type=EventType.TASK_COMPLETED_EARLY,
        task_id=first_task.id,
        new_value=original_hours * 0.5,
    )
    updated = planner.recalculate_plan(event)
    updated_task = updated.get_task(first_task.id)
    assert updated_task.status == TaskStatus.COMPLETED


def test_replan_task_added():
    planner = _base_planner()
    new_task = Task(
        name="Security audit",
        priority=TaskPriority.HIGH,
        required_skills=["backend"],
        estimated_hours=12.0,
    )
    event = ReplanningEvent(
        event_type=EventType.TASK_ADDED,
        new_value=new_task,
    )
    updated = planner.recalculate_plan(event)
    assert any(t.id == new_task.id for t in updated.tasks)


def test_replan_task_removed():
    planner = _base_planner()
    # Remove a non-critical leaf task to keep the graph valid
    leaf_task = next(
        t for t in planner.current_plan.tasks
        if t.name == "Write API documentation"
    )
    event = ReplanningEvent(
        event_type=EventType.TASK_REMOVED,
        task_id=leaf_task.id,
    )
    updated = planner.recalculate_plan(event)
    assert not any(t.id == leaf_task.id for t in updated.tasks)


def test_replan_resource_unavailable():
    planner = _base_planner()
    resource = planner.current_plan.resources[0]
    event = ReplanningEvent(
        event_type=EventType.RESOURCE_UNAVAILABLE,
        resource_id=resource.id,
    )
    updated = planner.recalculate_plan(event)
    updated_resource = updated.get_resource(resource.id)
    assert updated_resource.capacity == 0.0


def test_replan_capacity_changed():
    planner = _base_planner()
    resource = planner.current_plan.resources[0]
    event = ReplanningEvent(
        event_type=EventType.RESOURCE_CAPACITY_CHANGED,
        resource_id=resource.id,
        new_value=0.5,
    )
    updated = planner.recalculate_plan(event)
    updated_resource = updated.get_resource(resource.id)
    assert abs(updated_resource.capacity - 0.5) < 1e-6


def test_replan_dependency_changed():
    planner = _base_planner()
    task = planner.current_plan.tasks[-1]   # last task
    event = ReplanningEvent(
        event_type=EventType.DEPENDENCY_CHANGED,
        task_id=task.id,
        new_value=[],  # remove all dependencies
    )
    updated = planner.recalculate_plan(event)
    updated_task = updated.get_task(task.id)
    assert updated_task.dependencies == []


def test_update_dependencies_helper():
    planner = _base_planner()
    task = planner.current_plan.tasks[-1]
    updated = planner.update_dependencies(task.id, [])
    assert updated.get_task(task.id).dependencies == []


# ===========================================================================
# 5. Edge cases
# ===========================================================================

def test_single_task_plan():
    task = Task(name="Solo task", estimated_hours=8.0)
    resource = Resource(name="Solo Dev", skills=[], capacity=1.0)
    planner = ProjectPlanner(
        project_name="Solo",
        deadline=date.today() + timedelta(days=30),
        tasks=[task],
        resources=[resource],
    )
    plan = planner.build_initial_plan()
    assert len(plan.tasks) == 1
    assert plan.tasks[0].start_date is not None


def test_no_resources():
    tasks = [Task(name="Orphan task", estimated_hours=8.0)]
    planner = ProjectPlanner(
        project_name="No Resources",
        deadline=date.today() + timedelta(days=30),
        tasks=tasks,
        resources=[],
    )
    plan = planner.build_initial_plan()
    # Should not crash; task gets scheduled without assignment
    assert len(plan.tasks) == 1


def test_summary_dict():
    planner = _base_planner()
    summary = planner.summary()
    assert "project_name" in summary
    assert "is_on_time" in summary
    assert "total_tasks" in summary


# ===========================================================================
# Run all tests
# ===========================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(" AI Planning Module — Test Suite")
    print("=" * 60 + "\n")

    test_groups = {
        "1. Duration Estimation": [
            ("estimate_milestone",    test_estimate_milestone),
            ("estimate_keyword_match", test_estimate_keyword_match),
            ("fill_missing",           test_fill_missing),
        ],
        "2. Dependency Graph & CPM": [
            ("dag_builds_correctly",     test_dag_builds_correctly),
            ("dag_detects_cycle",        test_dag_detects_cycle),
            ("dag_roots_and_leaves",     test_dag_roots_and_leaves),
            ("cpm_produces_critical_path", test_cpm_produces_critical_path),
            ("cpm_forward_backward",     test_cpm_forward_backward),
        ],
        "3. Full Initial Plan": [
            ("build_initial_plan",         test_build_initial_plan),
            ("all_tasks_scheduled",        test_all_tasks_scheduled),
            ("dependency_ordering",        test_dependency_ordering_respected),
            ("resources_assigned",         test_resources_assigned),
            ("sprint_task_coverage",       test_sprint_task_coverage),
            ("plan_serialises_to_dict",    test_plan_serialises_to_dict),
        ],
        "4. Replanning Engine": [
            ("replan_completed_late",      test_replan_task_completed_late),
            ("replan_completed_early",     test_replan_task_completed_early),
            ("replan_task_added",          test_replan_task_added),
            ("replan_task_removed",        test_replan_task_removed),
            ("replan_resource_unavailable", test_replan_resource_unavailable),
            ("replan_capacity_changed",    test_replan_capacity_changed),
            ("replan_dependency_changed",  test_replan_dependency_changed),
            ("update_dependencies_helper", test_update_dependencies_helper),
        ],
        "5. Edge Cases": [
            ("single_task_plan",  test_single_task_plan),
            ("no_resources",      test_no_resources),
            ("summary_dict",      test_summary_dict),
        ],
    }

    total = passed = 0
    for group, tests in test_groups.items():
        print(f"\n{group}")
        print("-" * 50)
        for name, fn in tests:
            run_test(name, fn)
            total += 1
            if results[-1][0] == PASS:
                passed += 1

    print("\n" + "=" * 60)
    print(f" Results: {passed}/{total} tests passed")
    print("=" * 60 + "\n")

    sys.exit(0 if passed == total else 1)
