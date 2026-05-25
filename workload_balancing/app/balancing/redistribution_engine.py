"""
redistribution_engine.py
------------------------
Generates actionable, human-readable recommendations for workload
redistribution.  It NEVER executes any changes — all actions carry
requires_approval=True.

Strategy:
  1. Match overloaded employees with underutilized ones.
  2. Prefer receivers with high availability AND compatible skills.
  3. For bottleneck employees, recommend task-splitting or delay.
  4. Rank actions by urgency (priority field).
"""

from __future__ import annotations
import logging
from typing import List, Optional, Tuple

from app.models.schemas import (
    ActionType,
    Employee,
    RecommendedAction,
    Task,
    WorkloadMetrics,
)
from app.balancing.risk_analyzer import RiskReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MAX_ACTIONS = 10             # cap recommendations to keep output readable
MIN_AVAILABILITY_TO_RECEIVE = 40.0   # receiver must have ≥40 availability


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RedistributionEngine:
    """
    Generates a prioritised list of RecommendedAction objects.
    Thread-safe — no mutable state.
    """

    def generate(
        self,
        report: RiskReport,
        employees: List[Employee],
        tasks: Optional[List[Task]] = None,
        metrics: Optional[List[WorkloadMetrics]] = None,
    ) -> List[RecommendedAction]:
        actions: List[RecommendedAction] = []

        emp_map = {e.id: e for e in employees}
        metrics_map = {m.employee_id: m for m in (metrics or [])}

        # Build a pool of potential receivers (sorted by availability desc)
        receivers = sorted(
            [e for e in employees if e.availability_score >= MIN_AVAILABILITY_TO_RECEIVE],
            key=lambda e: e.availability_score,
            reverse=True,
        )

        # 1. Reassign tasks from overloaded → underutilized
        actions.extend(
            self._reassign_actions(
                report.overloaded, receivers, emp_map, tasks, metrics_map
            )
        )

        # 2. Flag bottleneck employees → split or delay
        actions.extend(
            self._bottleneck_actions(report.bottlenecks, emp_map, tasks)
        )

        # 3. General redistribute if variance is very high
        if report.score_variance > 400 and not report.overloaded:
            actions.extend(
                self._general_redistribute(employees, receivers, metrics_map)
            )

        # Deduplicate (same action+from+to+task), sort by priority desc, cap
        seen = set()
        unique: List[RecommendedAction] = []
        for a in sorted(actions, key=lambda x: x.priority, reverse=True):
            key = (a.action, a.from_employee, a.to_employee, a.task_id)
            if key not in seen:
                seen.add(key)
                unique.append(a)
            if len(unique) >= MAX_ACTIONS:
                break

        logger.info("RedistributionEngine: generated %d recommendations", len(unique))
        return unique

    # ------------------------------------------------------------------
    # Strategy implementations
    # ------------------------------------------------------------------

    def _reassign_actions(
        self,
        overloaded: List[WorkloadMetrics],
        receivers: List[Employee],
        emp_map: dict,
        tasks: Optional[List[Task]],
        metrics_map: dict,
    ) -> List[RecommendedAction]:
        actions: List[RecommendedAction] = []

        for sender_metric in overloaded:
            sender = emp_map.get(sender_metric.employee_id)
            if not sender:
                continue

            # Find best receiver
            receiver = self._best_receiver(sender, receivers, emp_map)
            if not receiver:
                actions.append(
                    RecommendedAction(
                        action=ActionType.FLAG_BOTTLENECK,
                        priority=9,
                        from_employee=sender.name,
                        reason=(
                            f"{sender.name} is overloaded (score {sender_metric.risk_score:.0f}) "
                            "but no suitable receiver found. Consider hiring or pausing intake."
                        ),
                        estimated_impact="Prevents further burnout risk.",
                        requires_approval=True,
                    )
                )
                continue

            # Pick the best task to move
            task = self._pick_task_to_move(sender, tasks)

            actions.append(
                RecommendedAction(
                    action=ActionType.REASSIGN_TASK,
                    priority=self._urgency(sender_metric.risk_score),
                    from_employee=sender.name,
                    to_employee=receiver.name,
                    task_id=task.id if task else None,
                    task_title=task.title if task else None,
                    reason=(
                        f"{sender.name} has a risk score of {sender_metric.risk_score:.0f} "
                        f"({sender_metric.reason}). "
                        f"{receiver.name} has {receiver.availability_score:.0f}% availability."
                    ),
                    estimated_impact=(
                        f"Expected to reduce {sender.name}'s workload score by ~15-25 points."
                    ),
                    requires_approval=True,
                )
            )

        return actions

    def _bottleneck_actions(
        self,
        bottlenecks: List[WorkloadMetrics],
        emp_map: dict,
        tasks: Optional[List[Task]],
    ) -> List[RecommendedAction]:
        actions: List[RecommendedAction] = []

        for b_metric in bottlenecks:
            emp = emp_map.get(b_metric.employee_id)
            if not emp:
                continue

            # Split recommendation for large tasks
            if emp.task_complexity_distribution.critical > 0:
                actions.append(
                    RecommendedAction(
                        action=ActionType.SPLIT_TASK,
                        priority=8,
                        from_employee=emp.name,
                        reason=(
                            f"{emp.name} holds {emp.task_complexity_distribution.critical} critical task(s) "
                            f"and {emp.delayed_tasks} delayed tasks — a classic bottleneck pattern."
                        ),
                        estimated_impact=(
                            "Splitting critical tasks reduces per-task risk and enables parallel progress."
                        ),
                        requires_approval=True,
                    )
                )

            # Delay low-priority tasks
            low_priority_task = self._pick_low_priority_task(emp, tasks)
            if low_priority_task:
                actions.append(
                    RecommendedAction(
                        action=ActionType.DELAY_TASK,
                        priority=6,
                        from_employee=emp.name,
                        task_id=low_priority_task.id,
                        task_title=low_priority_task.title,
                        reason=(
                            f"Delaying '{low_priority_task.title}' (priority {low_priority_task.priority}) "
                            f"frees cognitive bandwidth for {emp.name}'s delayed tasks."
                        ),
                        estimated_impact="Reduces active task count and improves focus.",
                        requires_approval=True,
                    )
                )

        return actions

    def _general_redistribute(
        self,
        employees: List[Employee],
        receivers: List[Employee],
        metrics_map: dict,
    ) -> List[RecommendedAction]:
        """Triggered when no one is critically overloaded but variance is high."""
        if len(employees) < 2:
            return []

        busiest = max(employees, key=lambda e: e.active_tasks)
        most_free = min(employees, key=lambda e: e.active_tasks)

        if busiest.id == most_free.id:
            return []

        return [
            RecommendedAction(
                action=ActionType.REDISTRIBUTE,
                priority=4,
                from_employee=busiest.name,
                to_employee=most_free.name,
                reason=(
                    f"High workload variance across team. {busiest.name} has "
                    f"{busiest.active_tasks} tasks vs {most_free.name}'s {most_free.active_tasks}."
                ),
                estimated_impact="Brings the team closer to balanced distribution.",
                requires_approval=True,
            )
        ]

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _best_receiver(
        sender: Employee,
        receivers: List[Employee],
        emp_map: dict,
    ) -> Optional[Employee]:
        for r in receivers:
            if r.id == sender.id:
                continue
            # Skill overlap is a bonus but not mandatory
            return r
        return None

    @staticmethod
    def _pick_task_to_move(
        emp: Employee, tasks: Optional[List[Task]]
    ) -> Optional[Task]:
        if not tasks:
            return None
        assigned = [t for t in tasks if t.assigned_to == emp.id and not t.is_delayed]
        if not assigned:
            return None
        # Move lowest-priority, lowest-complexity task
        return min(assigned, key=lambda t: (t.priority, t.complexity))

    @staticmethod
    def _pick_low_priority_task(
        emp: Employee, tasks: Optional[List[Task]]
    ) -> Optional[Task]:
        if not tasks:
            return None
        assigned = [t for t in tasks if t.assigned_to == emp.id and not t.is_delayed]
        if not assigned:
            return None
        return min(assigned, key=lambda t: t.priority)

    @staticmethod
    def _urgency(risk_score: float) -> int:
        if risk_score >= 85:
            return 10
        if risk_score >= 70:
            return 8
        if risk_score >= 55:
            return 6
        return 4
