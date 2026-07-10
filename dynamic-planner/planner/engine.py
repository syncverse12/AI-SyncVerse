"""
planner.py
----------
Complete AI Planning Engine — all scheduling logic in one file.

Modules inlined (previously separate files in planner/ package):
  utils.py            → calendar helpers + AI duration estimator
  dependency_graph.py → DAG construction + CPM
  scheduler.py        → resource levelling + calendar scheduling
  sprint_generator.py → heuristic sprint grouping
  replanning_engine.py→ event-driven dynamic replanning
  ProjectPlanner      → high-level facade (main entry point)

All imports are absolute (no relative dots) so this file works
in a flat single-directory layout.
"""

from __future__ import annotations

import copy
import logging
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

# Flat import — models.py lives in the same directory
from planner.models import (
    EventType,
    ProjectPlan,
    ReplanningEvent,
    Resource,
    Sprint,
    Task,
    TaskPriority,
    TaskStatus,
)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 — Logging helper
# ═══════════════════════════════════════════════════════════════════════════

def get_logger(name: str = "planner") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # Prevent double-logging: this logger already has its own handler,
    # so don't also let records bubble up to the root logger configured
    # in app/main.py (which has its own StreamHandler).
    logger.propagate = False
    return logger


logger = get_logger("planner.core")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2 — Calendar utilities
# ═══════════════════════════════════════════════════════════════════════════

WORKING_DAYS: set = {0, 1, 2, 3, 4}   # Monday=0 … Friday=4


def is_working_day(d: date) -> bool:
    return d.weekday() in WORKING_DAYS


def next_working_day(d: date) -> date:
    while not is_working_day(d):
        d += timedelta(days=1)
    return d


def add_working_days(start: date, working_days: float) -> date:
    full_days = math.ceil(working_days)
    current = next_working_day(start)
    added = 0
    while added < full_days:
        current += timedelta(days=1)
        if is_working_day(current):
            added += 1
    return current


def working_days_between(start: date, end: date) -> int:
    count = 0
    current = start
    while current < end:
        if is_working_day(current):
            count += 1
        current += timedelta(days=1)
    return count


def hours_to_working_days(hours: float, hours_per_day: float = 8.0) -> float:
    return hours / hours_per_day


def total_resource_hours_for_period(
    resources: List[Resource],
    start: date,
    end: date,
    hours_per_day: float = 8.0,
) -> float:
    total = 0.0
    day = start
    while day <= end:
        if is_working_day(day):
            for r in resources:
                total += r.effective_capacity_on(day) * hours_per_day
        day += timedelta(days=1)
    return total


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3 — AI Duration Estimator
# ═══════════════════════════════════════════════════════════════════════════

_KEYWORD_ESTIMATES: List[tuple] = [
    ({"design", "architect", "plan", "blueprint", "prototype"},    16.0),
    ({"research", "investigate", "analyse", "analyze", "spike"},    8.0),
    ({"implement", "develop", "build", "create", "code", "write"}, 24.0),
    ({"test", "qa", "review", "audit", "validate"},                12.0),
    ({"deploy", "release", "rollout", "launch"},                    8.0),
    ({"document", "docs", "readme", "spec"},                        6.0),
    ({"meeting", "sync", "standup", "demo", "presentation"},        2.0),
    ({"fix", "bug", "patch", "hotfix", "refactor"},               10.0),
    ({"migrate", "integration", "integrate"},                      20.0),
    ({"setup", "configure", "install", "onboard"},                  6.0),
]

_PRIORITY_MULTIPLIER: Dict[str, float] = {
    "low": 0.8, "medium": 1.0, "high": 1.2, "critical": 1.4,
}

_DEFAULT_HOURS = 8.0


def estimate_task_duration(task: Task) -> float:
    if task.is_milestone:
        return 0.0
    tokens = set((task.name + " " + task.description).lower().split())
    best_hours = _DEFAULT_HOURS
    best_overlap = 0
    for keywords, hours in _KEYWORD_ESTIMATES:
        overlap = len(keywords & tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_hours = hours
    priority_mult = _PRIORITY_MULTIPLIER.get(task.priority.value, 1.0)
    skill_count = max(len(task.required_skills), 1)
    skill_mult = min(1.0 + 0.2 * (skill_count - 1), 2.0)
    return round(best_hours * priority_mult * skill_mult, 1)


def fill_missing_estimates(tasks: List[Task]) -> List[Task]:
    for task in tasks:
        if task.estimated_hours is None or task.estimated_hours <= 0:
            task.estimated_hours = estimate_task_duration(task)
    return tasks


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4 — Dependency Graph + CPM
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CPMNode:
    task_id: str
    duration: float
    es: float = 0.0
    ef: float = 0.0
    ls: float = 0.0
    lf: float = 0.0
    total_float: float = 0.0
    free_float: float = 0.0

    @property
    def is_critical(self) -> bool:
        return abs(self.total_float) < 1e-6


class DependencyGraph:
    def __init__(self, tasks: List[Task], hours_per_day: float = 8.0):
        self.hours_per_day = hours_per_day
        self._tasks: Dict[str, Task] = {t.id: t for t in tasks}
        self._successors:   Dict[str, List[str]] = defaultdict(list)
        self._predecessors: Dict[str, List[str]] = defaultdict(list)
        self._build_graph()
        self._validate_no_cycles()

    def _build_graph(self) -> None:
        for task in self._tasks.values():
            for dep_id in task.dependencies:
                if dep_id not in self._tasks:
                    raise ValueError(
                        f"Task '{task.id}' depends on unknown task '{dep_id}'."
                    )
                self._predecessors[task.id].append(dep_id)
                self._successors[dep_id].append(task.id)

    def _validate_no_cycles(self) -> None:
        in_degree = {tid: len(preds) for tid, preds in self._predecessors.items()}
        for tid in self._tasks:
            in_degree.setdefault(tid, 0)
        queue = deque(tid for tid, deg in in_degree.items() if deg == 0)
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for succ in self._successors.get(node, []):
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)
        if visited != len(self._tasks):
            raise ValueError(
                "Cycle detected in task dependency graph. "
                "Please review your task dependencies."
            )

    def topological_order(self) -> List[str]:
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        in_degree = {tid: len(self._predecessors.get(tid, [])) for tid in self._tasks}
        ready: List[str] = [tid for tid, deg in in_degree.items() if deg == 0]
        ready.sort(key=lambda tid: priority_rank.get(self._tasks[tid].priority.value, 2))
        order: List[str] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            successors = sorted(
                self._successors.get(node, []),
                key=lambda tid: priority_rank.get(self._tasks[tid].priority.value, 2),
            )
            for succ in successors:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    ready.append(succ)
                    ready.sort(key=lambda tid: priority_rank.get(
                        self._tasks[tid].priority.value, 2))
        return order

    def predecessors(self, task_id: str) -> List[str]:
        return list(self._predecessors.get(task_id, []))

    def successors(self, task_id: str) -> List[str]:
        return list(self._successors.get(task_id, []))

    def roots(self) -> List[str]:
        return [tid for tid in self._tasks if not self._predecessors.get(tid)]

    def leaves(self) -> List[str]:
        return [tid for tid in self._tasks if not self._successors.get(tid)]

    def all_ancestors(self, task_id: str) -> Set[str]:
        visited: Set[str] = set()
        queue = deque(self._predecessors.get(task_id, []))
        while queue:
            node = queue.popleft()
            if node not in visited:
                visited.add(node)
                queue.extend(self._predecessors.get(node, []))
        return visited

    def all_descendants(self, task_id: str) -> Set[str]:
        visited: Set[str] = set()
        queue = deque(self._successors.get(task_id, []))
        while queue:
            node = queue.popleft()
            if node not in visited:
                visited.add(node)
                queue.extend(self._successors.get(node, []))
        return visited

    def compute_cpm(self) -> Tuple[Dict[str, CPMNode], List[str]]:
        topo = self.topological_order()
        nodes: Dict[str, CPMNode] = {}
        for tid in topo:
            task = self._tasks[tid]
            nodes[tid] = CPMNode(task_id=tid, duration=task.estimated_hours or 0.0)

        for tid in topo:
            node = nodes[tid]
            preds = self._predecessors.get(tid, [])
            node.es = max(nodes[p].ef for p in preds) if preds else 0.0
            node.ef = node.es + node.duration

        project_duration = max(nodes[tid].ef for tid in topo) if topo else 0.0

        for tid in reversed(topo):
            node = nodes[tid]
            succs = self._successors.get(tid, [])
            node.lf = min(nodes[s].ls for s in succs) if succs else project_duration
            node.ls = node.lf - node.duration

        for tid in topo:
            node = nodes[tid]
            node.total_float = node.ls - node.es
            succs = self._successors.get(tid, [])
            node.free_float = (
                min(nodes[s].es for s in succs) - node.ef if succs
                else project_duration - node.ef
            )

        critical_ids = {tid for tid, n in nodes.items() if n.is_critical}
        critical_path = self._longest_critical_path(critical_ids, topo)
        return nodes, critical_path

    def _longest_critical_path(self, critical_ids: Set[str], topo: List[str]) -> List[str]:
        best_prev: Dict[str, Optional[str]] = {tid: None for tid in critical_ids}
        best_dur:  Dict[str, float] = {
            tid: self._tasks[tid].estimated_hours or 0.0 for tid in critical_ids
        }
        for tid in topo:
            if tid not in critical_ids:
                continue
            for pred in self._predecessors.get(tid, []):
                if pred not in critical_ids:
                    continue
                candidate = best_dur[pred] + (self._tasks[tid].estimated_hours or 0.0)
                if candidate > best_dur[tid]:
                    best_dur[tid] = candidate
                    best_prev[tid] = pred
        if not best_dur:
            return []
        end_node = max(best_dur, key=lambda tid: best_dur[tid])
        path: List[str] = []
        current: Optional[str] = end_node
        while current is not None:
            path.append(current)
            current = best_prev[current]
        path.reverse()
        return path

    def add_task(self, task: Task) -> None:
        self._tasks[task.id] = task
        for dep_id in task.dependencies:
            if dep_id not in self._tasks:
                raise ValueError(f"Dependency '{dep_id}' not found in graph.")
            self._predecessors.setdefault(task.id, []).append(dep_id)
            self._successors.setdefault(dep_id, []).append(task.id)
        self._validate_no_cycles()

    def remove_task(self, task_id: str) -> None:
        if task_id not in self._tasks:
            return
        for pred in self._predecessors.get(task_id, []):
            succs = self._successors.get(pred, [])
            if task_id in succs:
                succs.remove(task_id)
        for succ in self._successors.get(task_id, []):
            preds = self._predecessors.get(succ, [])
            if task_id in preds:
                preds.remove(task_id)
        self._successors.pop(task_id, None)
        self._predecessors.pop(task_id, None)
        del self._tasks[task_id]

    def update_dependencies(self, task_id: str, new_deps: List[str]) -> None:
        if task_id not in self._tasks:
            raise ValueError(f"Task '{task_id}' not found in graph.")
        for old_dep in self._predecessors.get(task_id, []):
            succs = self._successors.get(old_dep, [])
            if task_id in succs:
                succs.remove(task_id)
        self._predecessors[task_id] = []
        for dep_id in new_deps:
            if dep_id not in self._tasks:
                raise ValueError(f"Dependency '{dep_id}' not found in graph.")
            self._predecessors[task_id].append(dep_id)
            self._successors.setdefault(dep_id, []).append(task_id)
        self._tasks[task_id].dependencies = list(new_deps)
        self._validate_no_cycles()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5 — Resource Load Tracker + Scheduling Engine
# ═══════════════════════════════════════════════════════════════════════════

class ResourceLoadTracker:
    def __init__(self, resources: List[Resource], hours_per_day: float = 8.0):
        self._resources = {r.id: r for r in resources}
        self._hours_per_day = hours_per_day
        self._load: Dict[str, Dict[date, float]] = defaultdict(lambda: defaultdict(float))

    def available_hours_on(self, resource_id: str, day: date) -> float:
        resource = self._resources.get(resource_id)
        if resource is None or not resource.is_available_on(day):
            return 0.0
        capacity = resource.capacity * self._hours_per_day
        committed = self._load[resource_id].get(day, 0.0)
        return max(capacity - committed, 0.0)

    def commit(self, resource_id: str, start: date, end: date, total_hours: float) -> None:
        working_days = self._working_days_list(start, end)
        if not working_days:
            return
        resource = self._resources.get(resource_id)
        if resource is None:
            return
        hours_per_working_day = resource.capacity * self._hours_per_day
        remaining = total_hours
        for day in working_days:
            if remaining <= 0:
                break
            available = self.available_hours_on(resource_id, day)
            allocated = min(available, remaining, hours_per_working_day)
            self._load[resource_id][day] += allocated
            remaining -= allocated

    def first_available_date(self, resource_id: str, earliest: date, required_daily_hours: float) -> date:
        day = next_working_day(earliest)
        for _ in range(365):
            if self.available_hours_on(resource_id, day) >= required_daily_hours - 1e-6:
                return day
            day += timedelta(days=1)
            while not is_working_day(day):
                day += timedelta(days=1)
        return day

    @staticmethod
    def _working_days_list(start: date, end: date) -> List[date]:
        days = []
        d = start
        while d <= end:
            if is_working_day(d):
                days.append(d)
            d += timedelta(days=1)
        return days


class SchedulingEngine:
    def __init__(self, resources: List[Resource], project_start: date, hours_per_day: float = 8.0):
        self._resources = resources
        self._project_start = next_working_day(project_start)
        self._hours_per_day = hours_per_day
        self._load_tracker = ResourceLoadTracker(resources, hours_per_day)

    def schedule(self, tasks: List[Task], cpm_nodes: Dict[str, CPMNode], topo_order: List[str]) -> List[Task]:
        task_map: Dict[str, Task] = {t.id: t for t in tasks}
        scheduled: Set[str] = set()
        for tid in topo_order:
            task = task_map.get(tid)
            if task is None:
                continue
            if task.is_complete:
                scheduled.add(tid)
                continue
            earliest_start = self._earliest_start(task, task_map, scheduled)
            resource = self._pick_resource(task, earliest_start)
            if resource is not None:
                start, end = self._compute_dates_with_resource(task, resource, earliest_start)
                task.assigned_to = resource.id
                self._load_tracker.commit(resource.id, start, end, task.estimated_hours or 0.0)
            else:
                start = earliest_start
                end = self._compute_end_date_unresourced(task, start)
            task.start_date = start
            task.end_date   = end
            scheduled.add(tid)
        return tasks

    def allocate_resources(self, tasks: List[Task]) -> List[Task]:
        for task in tasks:
            if task.assigned_to or task.is_complete or not task.start_date:
                continue
            resource = self._pick_resource(task, task.start_date)
            if resource:
                task.assigned_to = resource.id
                self._load_tracker.commit(
                    resource.id,
                    task.start_date,
                    task.end_date or task.start_date,
                    task.estimated_hours or 0.0,
                )
        return tasks

    def _earliest_start(self, task: Task, task_map: Dict[str, Task], scheduled: Set[str]) -> date:
        earliest = self._project_start
        for dep_id in task.dependencies:
            dep = task_map.get(dep_id)
            if dep and dep.end_date:
                candidate = next_working_day(dep.end_date + timedelta(days=1))
                if candidate > earliest:
                    earliest = candidate
        return earliest

    def _pick_resource(self, task: Task, earliest_start: date) -> Optional[Resource]:
        if not self._resources:
            return None
        best_resource: Optional[Resource] = None
        best_score = float("-inf")
        for resource in self._resources:
            if not resource.is_available_on(earliest_start):
                continue
            skill_score = len(set(task.required_skills) & set(resource.skills)) * 2.0
            load_score = self._load_ratio_score(resource.id, earliest_start)
            score = skill_score - load_score
            if score > best_score:
                best_score = score
                best_resource = resource
        return best_resource

    def _load_ratio_score(self, resource_id: str, from_date: date) -> float:
        resource = next((r for r in self._resources if r.id == resource_id), None)
        if resource is None:
            return 1.0
        total_capacity = 0.0
        total_committed = 0.0
        day = from_date
        days_counted = 0
        while days_counted < 5:
            if is_working_day(day):
                cap = resource.capacity * self._hours_per_day
                committed = self._load_tracker._load[resource_id].get(day, 0.0)
                total_capacity += cap
                total_committed += committed
                days_counted += 1
            day += timedelta(days=1)
        if total_capacity == 0:
            return 1.0
        return total_committed / total_capacity

    def _compute_dates_with_resource(self, task: Task, resource: Resource, earliest_start: date) -> Tuple[date, date]:
        hours = task.estimated_hours or self._hours_per_day
        daily_capacity = resource.capacity * self._hours_per_day
        start = self._load_tracker.first_available_date(
            resource.id, earliest_start, min(daily_capacity, hours)
        )
        working_days_needed = math.ceil(hours / max(daily_capacity, 1e-6))
        end = add_working_days(start, working_days_needed - 1)
        if end < start:
            end = start
        return start, end

    def _compute_end_date_unresourced(self, task: Task, start: date) -> date:
        hours = task.estimated_hours or self._hours_per_day
        days_needed = max(1, math.ceil(hours / self._hours_per_day))
        return add_working_days(start, days_needed - 1)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6 — Sprint Generator
# ═══════════════════════════════════════════════════════════════════════════

class SprintGenerator:
    def __init__(self, sprint_length_days: int = 14, hours_per_day: float = 8.0, max_load_ratio: float = 0.90):
        self._sprint_length = sprint_length_days
        self._hours_per_day = hours_per_day
        self._max_load_ratio = max_load_ratio

    def generate_sprints(
        self,
        tasks: List[Task],
        resources: List[Resource],
        critical_path: List[str],
        project_start: Optional[date] = None,
    ) -> Tuple[List[Sprint], List[Task]]:
        scheduled = [t for t in tasks if t.start_date and not t.is_complete]
        completed = [t for t in tasks if t.is_complete]
        if not scheduled:
            return [], tasks

        critical_ids = set(critical_path)
        sprint_windows = self._build_sprint_windows(scheduled, project_start)
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        scheduled_sorted = sorted(
            scheduled,
            key=lambda t: (
                0 if t.id in critical_ids else 1,
                t.start_date or date.max,
                priority_rank.get(t.priority.value, 2),
            ),
        )

        sprints: List[Sprint] = []
        for sprint_num, (win_start, win_end) in enumerate(sprint_windows, start=1):
            sprint_capacity = total_resource_hours_for_period(
                resources, win_start, win_end, self._hours_per_day
            )
            sprints.append(Sprint(id=sprint_num, start_date=win_start, end_date=win_end,
                                  capacity_hours=sprint_capacity))

        for task in scheduled_sorted:
            if not task.start_date:
                continue
            target_idx = self._find_target_sprint(task.start_date, sprint_windows)
            if target_idx is None:
                target_idx = len(sprints) - 1
            is_critical = task.id in critical_ids
            placed = False
            for offset in range(len(sprints) - target_idx):
                idx = target_idx + offset
                if idx >= len(sprints):
                    break
                sprint = sprints[idx]
                task_hours = task.estimated_hours or 0.0
                projected_load = sprint.planned_hours + task_hours
                load_ratio = projected_load / sprint.capacity_hours if sprint.capacity_hours > 0 else float("inf")
                if is_critical or load_ratio <= self._max_load_ratio:
                    sprint.task_ids.append(task.id)
                    sprint.planned_hours += task_hours
                    task.sprint_id = sprint.id
                    placed = True
                    break
            if not placed:
                last = sprints[-1]
                last.task_ids.append(task.id)
                last.planned_hours += task.estimated_hours or 0.0
                task.sprint_id = last.id

        return sprints, scheduled + completed

    def _build_sprint_windows(self, tasks: List[Task], project_start: Optional[date]) -> List[Tuple[date, date]]:
        if project_start:
            first_day = next_working_day(project_start)
        else:
            first_day = next_working_day(min(t.start_date for t in tasks if t.start_date))
        last_day = max(t.end_date for t in tasks if t.end_date)
        windows: List[Tuple[date, date]] = []
        current = first_day
        while current <= last_day:
            win_end = current + timedelta(days=self._sprint_length - 1)
            windows.append((current, win_end))
            current = next_working_day(win_end + timedelta(days=1))
        return windows

    def _find_target_sprint(self, task_start: date, windows: List[Tuple[date, date]]) -> Optional[int]:
        for idx, (win_start, win_end) in enumerate(windows):
            if win_start <= task_start <= win_end:
                return idx
        if task_start < windows[0][0]:
            return 0
        return None


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7 — Replanning Engine
# ═══════════════════════════════════════════════════════════════════════════

class ReplanningEngine:
    def __init__(self, sprint_length_days: int = 14, hours_per_day: float = 8.0):
        self._sprint_length = sprint_length_days
        self._hours_per_day = hours_per_day

    def recalculate_plan(self, plan: ProjectPlan, event: ReplanningEvent) -> ProjectPlan:
        new_plan = copy.deepcopy(plan)
        new_plan.warnings = []
        handlers = {
            EventType.TASK_COMPLETED_EARLY:        self._handle_task_completed,
            EventType.TASK_COMPLETED_LATE:         self._handle_task_completed,
            EventType.TASK_ADDED:                  self._handle_task_added,
            EventType.TASK_REMOVED:                self._handle_task_removed,
            EventType.RESOURCE_UNAVAILABLE:        self._handle_resource_unavailable,
            EventType.RESOURCE_CAPACITY_CHANGED:   self._handle_capacity_changed,
            EventType.DEPENDENCY_CHANGED:          self._handle_dependency_changed,
        }
        handler = handlers.get(event.event_type)
        if handler is None:
            new_plan.warnings.append(f"Unhandled event type: {event.event_type.value}")
            return new_plan
        affected_task_ids = handler(new_plan, event)
        self._rebuild_schedule(new_plan, affected_task_ids)
        if new_plan.completion_date and new_plan.completion_date > new_plan.deadline:
            delta = (new_plan.completion_date - new_plan.deadline).days
            new_plan.warnings.append(
                f"⚠ Deadline at risk: estimated completion is {delta} day(s) late "
                f"({new_plan.completion_date.isoformat()} vs deadline {new_plan.deadline.isoformat()})."
            )
        return new_plan

    def _handle_task_completed(self, plan: ProjectPlan, event: ReplanningEvent) -> Set[str]:
        task = plan.get_task(event.task_id or "")
        if task is None:
            plan.warnings.append(f"Task '{event.task_id}' not found; skipping.")
            return set()
        actual_hours = float(event.new_value or task.estimated_hours or 0.0)
        task.actual_hours = actual_hours
        task.status = TaskStatus.COMPLETED
        if event.event_type == EventType.TASK_COMPLETED_LATE and task.start_date:
            days_taken = hours_to_working_days(actual_hours, self._hours_per_day)
            task.end_date = add_working_days(task.start_date, max(0, days_taken - 1))
        graph = DependencyGraph(plan.tasks, self._hours_per_day)
        return graph.all_descendants(task.id)

    def _handle_task_added(self, plan: ProjectPlan, event: ReplanningEvent) -> Set[str]:
        new_task: Optional[Task] = event.new_value
        if not isinstance(new_task, Task):
            plan.warnings.append("TASK_ADDED event must carry a Task in new_value.")
            return set()
        plan.tasks.append(new_task)
        affected = {new_task.id}
        try:
            graph = DependencyGraph(plan.tasks, self._hours_per_day)
            affected |= graph.all_descendants(new_task.id)
        except ValueError as exc:
            plan.warnings.append(str(exc))
        return affected

    def _handle_task_removed(self, plan: ProjectPlan, event: ReplanningEvent) -> Set[str]:
        task = plan.get_task(event.task_id or "")
        if task is None:
            plan.warnings.append(f"Task '{event.task_id}' not found; skipping.")
            return set()
        try:
            graph = DependencyGraph(plan.tasks, self._hours_per_day)
            affected = graph.all_descendants(task.id)
        except ValueError:
            affected = set()
        for t in plan.tasks:
            if task.id in t.dependencies:
                t.dependencies.remove(task.id)
        plan.tasks = [t for t in plan.tasks if t.id != task.id]
        for sprint in plan.sprints:
            if task.id in sprint.task_ids:
                sprint.task_ids.remove(task.id)
                sprint.planned_hours -= task.estimated_hours or 0.0
        return affected

    def _handle_resource_unavailable(self, plan: ProjectPlan, event: ReplanningEvent) -> Set[str]:
        resource = plan.get_resource(event.resource_id or "")
        if resource is None:
            plan.warnings.append(f"Resource '{event.resource_id}' not found; skipping.")
            return set()
        resource.capacity = 0.0
        resource.available_until = date.today() - timedelta(days=1)
        affected_ids: Set[str] = set()
        for task in plan.tasks:
            if task.assigned_to == resource.id and not task.is_complete:
                task.assigned_to = None
                affected_ids.add(task.id)
                try:
                    graph = DependencyGraph(plan.tasks, self._hours_per_day)
                    affected_ids |= graph.all_descendants(task.id)
                except ValueError:
                    pass
        return affected_ids

    def _handle_capacity_changed(self, plan: ProjectPlan, event: ReplanningEvent) -> Set[str]:
        resource = plan.get_resource(event.resource_id or "")
        if resource is None:
            plan.warnings.append(f"Resource '{event.resource_id}' not found; skipping.")
            return set()
        resource.capacity = max(0.0, min(float(event.new_value or resource.capacity), 1.0))
        return {task.id for task in plan.tasks if task.assigned_to == resource.id and not task.is_complete}

    def _handle_dependency_changed(self, plan: ProjectPlan, event: ReplanningEvent) -> Set[str]:
        task = plan.get_task(event.task_id or "")
        if task is None:
            plan.warnings.append(f"Task '{event.task_id}' not found; skipping.")
            return set()
        task.dependencies = list(event.new_value or [])
        try:
            graph = DependencyGraph(plan.tasks, self._hours_per_day)
            return {task.id} | graph.all_descendants(task.id)
        except ValueError as exc:
            plan.warnings.append(str(exc))
            return {task.id}

    def _rebuild_schedule(self, plan: ProjectPlan, affected_ids: Set[str]) -> None:
        try:
            graph = DependencyGraph(plan.tasks, self._hours_per_day)
        except ValueError as exc:
            plan.warnings.append(f"Graph error during rebuild: {exc}")
            return
        cpm_nodes, critical_path = graph.compute_cpm()
        plan.critical_path = critical_path
        completed_dates = [t.end_date for t in plan.tasks if t.is_complete and t.end_date]
        project_start = next_working_day(
            max(completed_dates) + timedelta(days=1) if completed_dates else date.today()
        )
        for task in plan.tasks:
            if task.id in affected_ids and not task.is_complete:
                task.start_date = None
                task.end_date   = None
                task.sprint_id  = None
        engine = SchedulingEngine(plan.resources, project_start, self._hours_per_day)
        engine.schedule(plan.tasks, cpm_nodes, graph.topological_order())
        gen = SprintGenerator(self._sprint_length, self._hours_per_day)
        plan.sprints, plan.tasks = gen.generate_sprints(plan.tasks, plan.resources, critical_path)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8 — ProjectPlanner facade
# ═══════════════════════════════════════════════════════════════════════════

class ProjectPlanner:
    def __init__(
        self,
        project_name: str,
        deadline: date,
        tasks: List[Task],
        resources: List[Resource],
        project_start: Optional[date] = None,
        sprint_length_days: int = 14,
        hours_per_day: float = 8.0,
    ):
        self.project_name = project_name
        self.deadline = deadline
        self.tasks = tasks
        self.resources = resources
        self.project_start = project_start or date.today()
        self.sprint_length_days = sprint_length_days
        self.hours_per_day = hours_per_day
        self._current_plan: Optional[ProjectPlan] = None
        self._replanning_engine = ReplanningEngine(sprint_length_days, hours_per_day)

    def build_initial_plan(self) -> ProjectPlan:
        logger.info("Building initial plan for project '%s'…", self.project_name)
        fill_missing_estimates(self.tasks)
        try:
            graph = DependencyGraph(self.tasks, self.hours_per_day)
        except ValueError as exc:
            raise ValueError(f"Invalid dependency graph: {exc}") from exc
        cpm_nodes, critical_path = graph.compute_cpm()
        logger.info("Critical path (%d tasks): %s", len(critical_path),
                    " → ".join(critical_path[:8]) + ("…" if len(critical_path) > 8 else ""))
        scheduler = SchedulingEngine(self.resources, self.project_start, self.hours_per_day)
        scheduled_tasks = scheduler.schedule(self.tasks, cpm_nodes, graph.topological_order())
        sprint_gen = SprintGenerator(self.sprint_length_days, self.hours_per_day)
        sprints, all_tasks = sprint_gen.generate_sprints(
            scheduled_tasks, self.resources, critical_path, self.project_start
        )
        plan = ProjectPlan(
            project_name=self.project_name,
            deadline=self.deadline,
            tasks=all_tasks,
            sprints=sprints,
            resources=self.resources,
            critical_path=critical_path,
        )
        if plan.completion_date and plan.completion_date > self.deadline:
            delta = (plan.completion_date - self.deadline).days
            plan.warnings.append(
                f"⚠ Deadline risk: estimated completion "
                f"{plan.completion_date.isoformat()} is {delta} day(s) past "
                f"the deadline {self.deadline.isoformat()}."
            )
        else:
            logger.info("Plan is on schedule ✓  (completion %s)", plan.completion_date)
        self._current_plan = plan
        logger.info("Plan built: %d tasks, %d sprints, %d resources.",
                    len(all_tasks), len(sprints), len(self.resources))
        return plan

    def generate_sprints(self, tasks=None, resources=None, critical_path=None) -> List[Sprint]:
        tasks     = tasks     or (self._current_plan.tasks     if self._current_plan else self.tasks)
        resources = resources or (self._current_plan.resources if self._current_plan else self.resources)
        cp        = critical_path or (self._current_plan.critical_path if self._current_plan else [])
        gen = SprintGenerator(self.sprint_length_days, self.hours_per_day)
        sprints, updated_tasks = gen.generate_sprints(tasks, resources, cp, self.project_start)
        if self._current_plan:
            self._current_plan.sprints = sprints
            self._current_plan.tasks   = updated_tasks
        return sprints

    def recalculate_plan(self, event: ReplanningEvent) -> ProjectPlan:
        if self._current_plan is None:
            raise RuntimeError("No initial plan exists. Call build_initial_plan() first.")
        updated_plan = self._replanning_engine.recalculate_plan(self._current_plan, event)
        self._current_plan = updated_plan
        return updated_plan

    def update_dependencies(self, task_id: str, new_dependencies: List[str]) -> ProjectPlan:
        event = ReplanningEvent(
            event_type=EventType.DEPENDENCY_CHANGED,
            task_id=task_id,
            new_value=new_dependencies,
        )
        return self.recalculate_plan(event)

    def allocate_resources(self, tasks=None, resources=None) -> List[Task]:
        tasks     = tasks     or (self._current_plan.tasks     if self._current_plan else self.tasks)
        resources = resources or (self._current_plan.resources if self._current_plan else self.resources)
        scheduler = SchedulingEngine(resources, self.project_start, self.hours_per_day)
        updated = scheduler.allocate_resources(tasks)
        if self._current_plan:
            self._current_plan.tasks = updated
        return updated

    @property
    def current_plan(self) -> Optional[ProjectPlan]:
        return self._current_plan

    def summary(self) -> Dict:
        plan = self._current_plan
        if plan is None:
            return {"status": "no_plan"}
        return {
            "project_name": plan.project_name,
            "deadline": plan.deadline.isoformat(),
            "is_on_time": plan.is_on_time,
            "completion_date": plan.completion_date.isoformat() if plan.completion_date else None,
            "total_tasks": len(plan.tasks),
            "total_sprints": len(plan.sprints),
            "total_resources": len(plan.resources),
            "critical_path_length": len(plan.critical_path),
            "warnings": plan.warnings,
        }
