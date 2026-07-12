"""
engine/workload_engine.py
----------------------------
        AI Enrichment
                |
        Workload Engine    <-- you are here (NEVER calls the LLM directly)
                |
        Report Builder

Thin orchestration wrapper around the ORIGINAL, preserved
WorkloadMonitor -> RiskAnalyzer -> RedistributionEngine pipeline. This is
intentionally unchanged from the pre-refactor implementation — by the time
data reaches here it's already fully-formed Employee/Task objects,
regardless of whether they came from Backend, Demo, or AI enrichment.
"""

from __future__ import annotations
from typing import List

from app.balancing.workload_monitor import WorkloadMonitor
from app.balancing.risk_analyzer import RiskAnalyzer, RiskReport
from app.balancing.redistribution_engine import RedistributionEngine
from app.models.context import WorkloadContext
from app.models.schemas import RecommendedAction, WorkloadMetrics
from app.core.logging import get_logger, timed

logger = get_logger(__name__)


class WorkloadEngineResult:
    def __init__(self, metrics: List[WorkloadMetrics], risk_report: RiskReport, actions: List[RecommendedAction]):
        self.metrics = metrics
        self.risk_report = risk_report
        self.actions = actions


class WorkloadEngine:
    def __init__(self) -> None:
        self._monitor = WorkloadMonitor()
        self._analyser = RiskAnalyzer()
        self._redistributor = RedistributionEngine()

    def run(self, context: WorkloadContext) -> WorkloadEngineResult:
        with timed(logger, "workload_engine_run", scope_id=context.scope_id):
            metrics = self._monitor.analyse(context.employees)
            risk_report = self._analyser.analyse(metrics)
            actions = self._redistributor.generate(
                report=risk_report,
                employees=context.employees,
                tasks=context.tasks,
                metrics=metrics,
            )
        return WorkloadEngineResult(metrics=metrics, risk_report=risk_report, actions=actions)
