"""
balancer_service.py
-------------------
Orchestrates the FULL pipeline:

    Data Provider -> Context Builder -> Metrics Engine -> AI Enrichment
        -> Workload Engine -> Report Builder

Also preserves the original direct-payload path (`analyse`) for backward
compatibility, and the SSE/WebSocket real-time broadcast queue.
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.ai.enrichment import AIEnrichmentLayer
from app.context.builder import ContextBuilder
from app.core.exceptions import WorkloadServiceError
from app.engine.metrics_engine import MetricsEngine
from app.engine.workload_engine import WorkloadEngine
from app.models.schemas import (
    BalanceReport,
    BalanceStatus,
    Employee,
    Task,
    WorkloadEvent,
    WorkloadUpdateRequest,
    WorkloadUpdateResponse,
)
from app.providers.factory import get_data_provider
from app.report.report_builder import ReportBuilder

logger = logging.getLogger(__name__)


class BalancerService:
    """
    Application-level singleton (registered in lifespan).
    Thread/async-safe because asyncio.Queue is used for fan-out.
    """

    def __init__(self) -> None:
        self._context_builder = ContextBuilder()
        self._metrics_engine = MetricsEngine()
        self._ai_enrichment = AIEnrichmentLayer()
        self._workload_engine = WorkloadEngine()
        self._report_builder = ReportBuilder()

        self._subscribers: Set[asyncio.Queue] = set()
        self._last_report: Optional[BalanceReport] = None
        self._last_full_report: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Full pipeline — provider-driven (Demo or Production, per APP_MODE)
    # ------------------------------------------------------------------

    async def analyse_scope(self, scope_type: str, scope_id: str) -> Dict[str, Any]:
        provider = get_data_provider()

        try:
            snapshot = await provider.get_team_snapshot(scope_type, scope_id)
            context = self._context_builder.build(snapshot, source=provider.mode)
            deterministic_metrics = self._metrics_engine.compute(context)
            context = await self._ai_enrichment.enrich(context)
            engine_result = self._workload_engine.run(context)
            full_report = self._report_builder.build(context, engine_result, deterministic_metrics)
        except WorkloadServiceError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("analyse_scope failed unexpectedly")
            raise WorkloadServiceError(str(exc)) from exc

        self._last_full_report = full_report
        report = BalanceReport(**full_report["report"])
        self._last_report = report

        event = WorkloadEvent(
            event_type=self._event_type(report.status),
            payload=full_report,
            timestamp=_now(),
        )
        await self._broadcast(event)
        return full_report

    async def list_scopes(self) -> List[dict]:
        provider = get_data_provider()
        return await provider.list_available_scopes()

    # ------------------------------------------------------------------
    # Legacy direct-payload path — preserved for backward compatibility.
    # No provider, no AI: caller supplies employees/tasks directly, exactly
    # like the pre-refactor API contract.
    # ------------------------------------------------------------------

    async def analyse(self, request: WorkloadUpdateRequest) -> WorkloadUpdateResponse:
        report = self._run_deterministic_pipeline(request.employees, request.tasks)
        self._last_report = report

        event = WorkloadEvent(
            event_type=self._event_type(report.status),
            payload=report.model_dump(),
            timestamp=_now(),
        )
        await self._broadcast(event)
        return WorkloadUpdateResponse(report=report)

    def _run_deterministic_pipeline(
        self, employees: List[Employee], tasks: Optional[List[Task]]
    ) -> BalanceReport:
        metrics = self._workload_engine._monitor.analyse(employees)
        risk_report = self._workload_engine._analyser.analyse(metrics)
        actions = self._workload_engine._redistributor.generate(
            report=risk_report, employees=employees, tasks=tasks, metrics=metrics,
        )
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
    # Real-time subscribers (SSE / WebSocket)
    # ------------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subscribers.add(q)
        logger.debug("New subscriber. Total: %d", len(self._subscribers))
        if self._last_full_report:
            catchup = WorkloadEvent(
                event_type="status_update", payload=self._last_full_report, timestamp=_now(),
            )
            q.put_nowait(catchup)
        elif self._last_report:
            catchup = WorkloadEvent(
                event_type="status_update", payload=self._last_report.model_dump(), timestamp=_now(),
            )
            q.put_nowait(catchup)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)
        logger.debug("Subscriber removed. Total: %d", len(self._subscribers))

    async def ping_all(self) -> None:
        await self._broadcast(WorkloadEvent(event_type="ping", payload={}, timestamp=_now()))

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

    @staticmethod
    def _event_type(status: BalanceStatus) -> str:
        mapping = {
            BalanceStatus.BALANCED: "status_update",
            BalanceStatus.IMBALANCE_DETECTED: "risk_alert",
            BalanceStatus.CRITICAL_IMBALANCE: "risk_alert",
        }
        return mapping.get(status, "status_update")


_service: Optional[BalancerService] = None


def get_balancer_service() -> BalancerService:
    global _service
    if _service is None:
        _service = BalancerService()
    return _service


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
