"""
dependency_graph.py
-------------------
Directed Acyclic Graph (DAG) for task dependencies.

Responsibilities
----------------
* Build and validate the task dependency graph.
* Detect cycles (raises ValueError early so the planner never gets bad data).
* Compute topological ordering for scheduling.
* Implement the Critical Path Method (CPM):
    - Forward pass  → earliest start (ES) / earliest finish (EF)
    - Backward pass → latest start (LS)   / latest finish (LF)
    - Float / slack calculation
    - Critical path extraction
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .models import Task


# ---------------------------------------------------------------------------
# CPM node — all times in hours relative to project start (hour 0)
# ---------------------------------------------------------------------------

@dataclass
class CPMNode:
    task_id: str
    duration: float        # hours

    es: float = 0.0        # earliest start
    ef: float = 0.0        # earliest finish  (= es + duration)
    ls: float = 0.0        # latest start
    lf: float = 0.0        # latest finish    (= ls + duration)
    total_float: float = 0.0   # ls - es  (== lf - ef)
    free_float: float = 0.0    # slack before delaying a *successor*

    @property
    def is_critical(self) -> bool:
        return abs(self.total_float) < 1e-6   # float comparison guard


# ---------------------------------------------------------------------------
# DependencyGraph
# ---------------------------------------------------------------------------

class DependencyGraph:
    """
    Thin wrapper around an adjacency list representation of the task DAG.

    Parameters
    ----------
    tasks : list of Task objects that form the project scope.
    hours_per_day : working-hours conversion factor used when mapping
                    CPM hour-offsets back to calendar dates.
    """

    def __init__(self, tasks: List[Task], hours_per_day: float = 8.0):
        self.hours_per_day = hours_per_day
        self._tasks: Dict[str, Task] = {t.id: t for t in tasks}

        # adjacency lists
        self._successors:   Dict[str, List[str]] = defaultdict(list)
        self._predecessors: Dict[str, List[str]] = defaultdict(list)

        self._build_graph()
        self._validate_no_cycles()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> None:
        """Populate successor / predecessor maps from task dependency lists."""
        for task in self._tasks.values():
            for dep_id in task.dependencies:
                if dep_id not in self._tasks:
                    raise ValueError(
                        f"Task '{task.id}' depends on unknown task '{dep_id}'."
                    )
                # dep_id → task  means dep_id is a predecessor of task
                self._predecessors[task.id].append(dep_id)
                self._successors[dep_id].append(task.id)

    def _validate_no_cycles(self) -> None:
        """Kahn's algorithm to detect cycles in the DAG."""
        in_degree = {tid: len(preds) for tid, preds in self._predecessors.items()}
        # ensure every task appears, even those with no predecessors
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

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    def topological_order(self) -> List[str]:
        """
        Return task IDs in a valid topological order (Kahn's BFS).
        Ties are broken by priority (CRITICAL > HIGH > MEDIUM > LOW)
        so higher-priority tasks are scheduled first within the same
        dependency level.
        """
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        in_degree = {tid: len(self._predecessors.get(tid, [])) for tid in self._tasks}
        # Use a list-based priority queue (small N; no need for heapq complexity)
        ready: List[str] = [tid for tid, deg in in_degree.items() if deg == 0]
        ready.sort(key=lambda tid: priority_rank.get(
            self._tasks[tid].priority.value, 2
        ))

        order: List[str] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            successors = sorted(
                self._successors.get(node, []),
                key=lambda tid: priority_rank.get(
                    self._tasks[tid].priority.value, 2
                ),
            )
            for succ in successors:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    ready.append(succ)
                    ready.sort(key=lambda tid: priority_rank.get(
                        self._tasks[tid].priority.value, 2
                    ))

        return order

    def predecessors(self, task_id: str) -> List[str]:
        return list(self._predecessors.get(task_id, []))

    def successors(self, task_id: str) -> List[str]:
        return list(self._successors.get(task_id, []))

    def roots(self) -> List[str]:
        """Tasks with no predecessors (project entry points)."""
        return [tid for tid in self._tasks if not self._predecessors.get(tid)]

    def leaves(self) -> List[str]:
        """Tasks with no successors (project terminal tasks)."""
        return [tid for tid in self._tasks if not self._successors.get(tid)]

    def all_ancestors(self, task_id: str) -> Set[str]:
        """BFS to collect the full transitive predecessor set."""
        visited: Set[str] = set()
        queue = deque(self._predecessors.get(task_id, []))
        while queue:
            node = queue.popleft()
            if node not in visited:
                visited.add(node)
                queue.extend(self._predecessors.get(node, []))
        return visited

    def all_descendants(self, task_id: str) -> Set[str]:
        """BFS to collect the full transitive successor set."""
        visited: Set[str] = set()
        queue = deque(self._successors.get(task_id, []))
        while queue:
            node = queue.popleft()
            if node not in visited:
                visited.add(node)
                queue.extend(self._successors.get(node, []))
        return visited

    # ------------------------------------------------------------------
    # Critical Path Method (CPM)
    # ------------------------------------------------------------------

    def compute_cpm(self) -> Tuple[Dict[str, CPMNode], List[str]]:
        """
        Run a full CPM analysis on the current task graph.

        Returns
        -------
        nodes        : mapping task_id → CPMNode with ES/EF/LS/LF/float.
        critical_path: ordered list of task IDs that form the critical path
                       (longest path from any root to any leaf).
        """
        topo = self.topological_order()
        nodes: Dict[str, CPMNode] = {}

        for tid in topo:
            task = self._tasks[tid]
            dur = task.estimated_hours or 0.0
            nodes[tid] = CPMNode(task_id=tid, duration=dur)

        # ---------- Forward pass (compute ES / EF) ----------
        for tid in topo:
            node = nodes[tid]
            preds = self._predecessors.get(tid, [])
            if not preds:
                node.es = 0.0
            else:
                node.es = max(nodes[p].ef for p in preds)
            node.ef = node.es + node.duration

        # Project duration = max EF across all leaves
        project_duration = max(nodes[tid].ef for tid in topo) if topo else 0.0

        # ---------- Backward pass (compute LS / LF) ----------
        for tid in reversed(topo):
            node = nodes[tid]
            succs = self._successors.get(tid, [])
            if not succs:
                node.lf = project_duration
            else:
                node.lf = min(nodes[s].ls for s in succs)
            node.ls = node.lf - node.duration

        # ---------- Float & free float ----------
        for tid in topo:
            node = nodes[tid]
            node.total_float = node.ls - node.es
            succs = self._successors.get(tid, [])
            if succs:
                node.free_float = min(nodes[s].es for s in succs) - node.ef
            else:
                node.free_float = project_duration - node.ef

        # ---------- Extract critical path ----------
        critical_ids = {tid for tid, n in nodes.items() if n.is_critical}
        critical_path = self._longest_critical_path(critical_ids, topo)

        return nodes, critical_path

    def _longest_critical_path(
        self, critical_ids: Set[str], topo: List[str]
    ) -> List[str]:
        """
        Among all paths that only traverse critical nodes, return the one
        that produces the largest total duration (the main critical path).
        """
        # DP: longest duration path ending at each critical node
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

        # Walk backwards to reconstruct path
        path: List[str] = []
        current: Optional[str] = end_node
        while current is not None:
            path.append(current)
            current = best_prev[current]
        path.reverse()
        return path

    # ------------------------------------------------------------------
    # Mutation helpers (used by ReplanningEngine)
    # ------------------------------------------------------------------

    def add_task(self, task: Task) -> None:
        """Add a new task and wire up its dependencies."""
        self._tasks[task.id] = task
        for dep_id in task.dependencies:
            if dep_id not in self._tasks:
                raise ValueError(f"Dependency '{dep_id}' not found in graph.")
            self._predecessors.setdefault(task.id, []).append(dep_id)
            self._successors.setdefault(dep_id, []).append(task.id)
        self._validate_no_cycles()

    def remove_task(self, task_id: str) -> None:
        """Remove a task and clean up all edges referencing it."""
        if task_id not in self._tasks:
            return
        # Remove from successor lists of its predecessors
        for pred in self._predecessors.get(task_id, []):
            succs = self._successors.get(pred, [])
            if task_id in succs:
                succs.remove(task_id)
        # Remove from predecessor lists of its successors
        for succ in self._successors.get(task_id, []):
            preds = self._predecessors.get(succ, [])
            if task_id in preds:
                preds.remove(task_id)
        self._successors.pop(task_id, None)
        self._predecessors.pop(task_id, None)
        del self._tasks[task_id]

    def update_dependencies(self, task_id: str, new_deps: List[str]) -> None:
        """Replace the dependency list of an existing task."""
        if task_id not in self._tasks:
            raise ValueError(f"Task '{task_id}' not found in graph.")
        # Tear down old edges
        for old_dep in self._predecessors.get(task_id, []):
            succs = self._successors.get(old_dep, [])
            if task_id in succs:
                succs.remove(task_id)
        self._predecessors[task_id] = []

        # Wire new edges
        for dep_id in new_deps:
            if dep_id not in self._tasks:
                raise ValueError(f"Dependency '{dep_id}' not found in graph.")
            self._predecessors[task_id].append(dep_id)
            self._successors.setdefault(dep_id, []).append(task_id)

        self._tasks[task_id].dependencies = list(new_deps)
        self._validate_no_cycles()

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"DependencyGraph("
            f"tasks={len(self._tasks)}, "
            f"edges={sum(len(v) for v in self._successors.values())})"
        )
