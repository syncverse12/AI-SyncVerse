"""
balancer_service.py
-------------------
Orchestrates the full workload-balancing pipeline:

    WorkloadMonitor → RiskAnalyzer → RedistributionEngine → BalanceReport

Also manages the real-time broadcast queue consumed by the SSE / WebSocket
route handlers.
"""

from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Set

from app.balancing.workload_monitor import WorkloadMonitor
from app.balancing.risk_analyzer import RiskAnalyzer
from app.balancing.redistribution_engine import RedistributionEngine
from app.models.schemas import (
    BalanceReport,
    BalanceStatus,
    Employee,
    Task,
    WorkloadEvent,
    WorkloadUpdateRequest,
    WorkloadUpdateResponse,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class BalancerService:
    """
    Application-level singleton (registered in lifespan).
    Thread/async-safe because asyncio.Queue is used for fan-out.
    """

    def __init__(self) -> None:
        self._monitor = WorkloadMonitor()
        self._analyser = RiskAnalyzer()
        self._engine = RedistributionEngine()

        # Active SSE subscriber queues
        self._subscribers: Set[asyncio.Queue] = set()

        # Last known report (for new subscribers to catch up)
        self._last_report: Optional[BalanceReport] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyse(self, request: WorkloadUpdateRequest) -> WorkloadUpdateResponse:
        """
        Run the full pipeline and broadcast an event to all subscribers.
        """
        report = self._run_pipeline(request.employees, request.tasks)
        self._last_report = report

        # Broadcast to all SSE/WS listeners
        event = WorkloadEvent(
            event_type=self._event_type(report.status),
            payload=report.dict(),
            timestamp=_now(),
        )
        await self._broadcast(event)

        return WorkloadUpdateResponse(report=report)

    def subscribe(self) -> asyncio.Queue:
        """Register a new real-time subscriber."""
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subscribers.add(q)
        logger.debug("New subscriber. Total: %d", len(self._subscribers))

        # Immediately send the last known state so the client isn't blank
        if self._last_report:
            catchup = WorkloadEvent(
                event_type="status_update",
                payload=self._last_report.dict(),
                timestamp=_now(),
            )
            q.put_nowait(catchup)

        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)
        logger.debug("Subscriber removed. Total: %d", len(self._subscribers))

    async def ping_all(self) -> None:
        """Heartbeat — keeps SSE connections alive."""
        await self._broadcast(
            WorkloadEvent(event_type="ping", payload={}, timestamp=_now())
        )

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        employees: List[Employee],
        tasks: Optional[List[Task]],
    ) -> BalanceReport:
        # 1. Score
        metrics = self._monitor.analyse(employees)

        # 2. Classify
        risk_report = self._analyser.analyse(metrics)

        # 3. Recommend
        actions = self._engine.generate(
            report=risk_report,
            employees=employees,
            tasks=tasks,
            metrics=metrics,
        )

        # 4. Assemble final report
        return BalanceReport(
            status=risk_report.status,
            timestamp=_now(),
            team_health_score=risk_report.team_health_score,
            overloaded_employees=risk_report.overloaded,
            underutilized_employees=risk_report.underutilized,
            bottleneck_employees=risk_report.bottlenecks,
            recommended_actions=actions,
            summary=risk_report.summary,
            metrics={
                "total_employees": len(employees),
                "overloaded_count": len(risk_report.overloaded),
                "underutilized_count": len(risk_report.underutilized),
                "bottleneck_count": len(risk_report.bottlenecks),
                "score_variance": risk_report.score_variance,
                "action_count": len(actions),
            },
        )

    # ------------------------------------------------------------------
    # Fan-out broadcast
    # ------------------------------------------------------------------

    async def _broadcast(self, event: WorkloadEvent) -> None:
        dead: List[asyncio.Queue] = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue full — dropping event")
            except Exception as exc:
                logger.error("Error broadcasting to subscriber: %s", exc)
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _event_type(status: BalanceStatus) -> str:
        mapping = {
            BalanceStatus.BALANCED: "status_update",
            BalanceStatus.IMBALANCE_DETECTED: "risk_alert",
            BalanceStatus.CRITICAL_IMBALANCE: "risk_alert",
        }
        return mapping.get(status, "status_update")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: Optional[BalancerService] = None


def get_balancer_service() -> BalancerService:
    global _service
    if _service is None:
        _service = BalancerService()
    return _service


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
