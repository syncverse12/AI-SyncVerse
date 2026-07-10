"""
Real-Time Pipeline Engine
==========================
Coordinates all agents in the correct order, streams partial results
via WebSocket after each agent completes, and emits a final ranking.

Pipeline stages (each broadcasts an intermediate WS message):
  0. Task received
  1. Task Understanding Agent
  2. Skill Matching Agent       ┐ run concurrently
  3. Workload Monitoring Agent  ┘
  4. Seniority Fit Agent
  5. Decision Orchestrator Agent → final result
"""
import asyncio
import time
import uuid
import logging
from typing import List

from app.models.schemas import TaskInput, TaskRequirements, FinalResult, EmployeeRecommendation
from app.models.employee_store import employee_store
from app.websocket.manager import manager
from app.agents.task_agent import task_agent
from app.agents.skill_agent import skill_agent
from app.agents.workload_agent import workload_agent
from app.agents.seniority_agent import seniority_agent
from app.agents.decision_agent import decision_agent

logger = logging.getLogger(__name__)


def _make_event(event: str, task_id: str, payload: dict) -> dict:
    return {"event": event, "task_id": task_id, "ts": time.time(), **payload}


async def run_task_pipeline(task: TaskInput, task_id: str | None = None) -> FinalResult:
    """
    Full async pipeline.  Streams WS events at every stage.
    Returns the FinalResult when done (also emitted via WS).

    Errors are caught, logged, broadcast as an "error" WS event, and
    re-raised. This matters because the two callers behave very differently
    if an exception escapes unhandled:
      - /analyze-task fires this via BackgroundTasks. FastAPI/Starlette does
        NOT propagate background-task exceptions back to the HTTP response —
        it already returned 200 with a task_id. Previously, a mid-pipeline
        crash meant the client just sat there with an open WebSocket that
        never received anything else, with no server-side signal at all.
      - /analyze-task/sync awaits this directly, so an uncaught exception
        here becomes an unhandled 500 with no clean error body.
    """
    if task_id is None:
        task_id = str(uuid.uuid4())

    try:
        return await _run_pipeline_stages(task, task_id)
    except Exception as exc:
        logger.exception(f"Pipeline failed  task_id={task_id}: {exc}")
        await manager.send_to_task(
            task_id,
            _make_event("error", task_id, {
                "status": "error",
                "message": "Task analysis failed. Please try again.",
            }),
        )
        raise


async def _run_pipeline_stages(task: TaskInput, task_id: str) -> FinalResult:
    updates: List[str] = []

    async def emit(event: str, msg: str, data: dict | None = None):
        updates.append(msg)
        payload = {"message": msg}
        if data:
            payload["data"] = data
        await manager.send_to_task(task_id, _make_event(event, task_id, payload))

    # ── Stage 0: Task received ────────────────────────────────────────────────
    await emit("task_received", "Task received → starting analysis pipeline…")

    # ── Stage 1: Task Understanding Agent ────────────────────────────────────
    await emit("agent_start", "Task Understanding Agent running…",
               {"agent": "task_agent", "status": "running"})

    employees = await employee_store.get_all()
    requirements: TaskRequirements = await task_agent.run(task.description)

    await emit("agent_done", "Task Understanding Agent complete",
               {
                   "agent": "task_agent",
                   "status": "done",
                   "requirements": requirements.model_dump(),
               })

    # ── Stage 2 + 3: Skill Matching & Workload Monitoring (concurrent) ───────
    await emit("agent_start", "Skill Matching + Workload Monitoring agents running in parallel…",
               {"agents": ["skill_agent", "workload_agent"], "status": "running"})

    skill_task    = asyncio.create_task(skill_agent.run(requirements, employees))
    workload_task = asyncio.create_task(workload_agent.run(employees))

    skill_scores, workload_scores = await asyncio.gather(skill_task, workload_task)

    await emit("agent_done", "Skill Matching Agent complete",
               {
                   "agent": "skill_agent",
                   "status": "done",
                   "top_matches": [
                       {"name": r.employee_name, "score": r.skill_score}
                       for r in skill_scores[:3]
                   ],
               })
    await emit("agent_done", "Workload Monitoring Agent complete",
               {
                   "agent": "workload_agent",
                   "status": "done",
                   "top_available": [
                       {"name": r.employee_name, "workload_score": r.workload_score}
                       for r in workload_scores[:3]
                   ],
               })

    # ── Stage 4: Seniority Fit Agent ─────────────────────────────────────────
    await emit("agent_start", "Seniority Fit Agent running…",
               {"agent": "seniority_agent", "status": "running"})

    seniority_scores = await seniority_agent.run(
        requirements.seniority_level,
        requirements.complexity,
        employees,
    )

    await emit("agent_done", "Seniority Fit Agent complete",
               {
                   "agent": "seniority_agent",
                   "status": "done",
                   "top_fits": [
                       {"name": r.employee_name, "seniority_score": r.seniority_score}
                       for r in seniority_scores[:3]
                   ],
               })

    # ── Stage 5: Decision Orchestrator ───────────────────────────────────────
    await emit("agent_start", "Decision Orchestrator synthesising final ranking…",
               {"agent": "decision_agent", "status": "running"})

    recommendations: List[EmployeeRecommendation] = await decision_agent.run(
        requirements,
        employees,
        skill_scores,
        workload_scores,
        seniority_scores,
    )

    await emit("agent_done", "Decision Orchestrator complete – top candidates identified",
               {
                   "agent": "decision_agent",
                   "status": "done",
                   "preview": [
                       {"rank": r.rank, "name": r.name, "score": r.final_score}
                       for r in recommendations[:3]
                   ],
               })

    # ── Final result ──────────────────────────────────────────────────────────
    final = FinalResult(
        task_id                = task_id,
        status                 = "complete",
        task_requirements      = requirements,
        updates                = updates,
        final_recommendations  = recommendations,
    )

    await manager.send_to_task(
        task_id,
        _make_event("final_result", task_id, {
            "status": "complete",
            "final_result": final.model_dump(),
        }),
    )

    logger.info(f"Pipeline complete  task_id={task_id}  "
                f"top={recommendations[0].name if recommendations else 'N/A'}")
    return final
