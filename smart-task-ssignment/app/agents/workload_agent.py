"""
Agent 3 – Workload Monitoring Agent
=====================================
Evaluates each employee's current workload and produces
a normalised availability score (0–100).

Formula:
  base_score   = availability_score (from store)
  task_penalty = active_tasks * 8   (each active task costs 8 pts)
  workload_score = clamp(base_score - task_penalty, 0, 100)

In production this agent would subscribe to a task-queue event stream
(Kafka / Redis Streams) and emit updates in real-time.
"""
import asyncio
import logging
from typing import List

from app.models.schemas import Employee, WorkloadScore

logger = logging.getLogger(__name__)

# Penalty per active task (tuneable)
TASK_PENALTY_PER_ACTIVE = 8.0
# Maximum active tasks before score hits 0
MAX_ACTIVE_TASKS = 10


class WorkloadMonitoringAgent:
    """Computes workload-based availability scores for all employees."""

    name = "Workload Monitoring Agent"

    async def run(self, employees: List[Employee]) -> List[WorkloadScore]:
        logger.info(f"[{self.name}] Evaluating workload for {len(employees)} employees…")
        await asyncio.sleep(0.15)   # simulate real-time poll latency

        results: List[WorkloadScore] = []
        for emp in employees:
            penalty = min(emp.active_tasks * TASK_PENALTY_PER_ACTIVE,
                          emp.availability_score)
            score = round(max(emp.availability_score - penalty, 0.0), 2)

            results.append(WorkloadScore(
                employee_id   = emp.id,
                employee_name = emp.name,
                workload_score = score,
            ))

        results.sort(key=lambda r: r.workload_score, reverse=True)
        top = results[0] if results else None
        logger.info(
            f"[{self.name}] Done – most available: "
            f"{top.employee_name if top else 'N/A'} ({top.workload_score if top else 0})"
        )
        return results


workload_agent = WorkloadMonitoringAgent()
