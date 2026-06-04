"""
Risk Service — the main orchestration layer.

Ties together:
  - Rule-based scoring
  - ML predictions
  - RAG historical retrieval
  - AI reasoning (LLM)
  - Alert engine
  - Persistence
  - Redis caching
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis

from app.ai.orchestrators.ai_orchestrator import AIOrchestrator
from app.ai.prompts.risk_prompts import (
    LIVE_UPDATE_SYSTEM,
    LIVE_UPDATE_USER,
    PRE_PROJECT_SYSTEM,
    PRE_PROJECT_USER,
)
from app.alerts.alert_engine import AlertEngine
from app.core.config import settings
from app.core.logging import get_logger
from app.ml.models.predictor import MLPredictor
from app.models.schemas import (
    CategoryRiskScore,
    HistoricalSimilarCase,
    LiveProjectMetrics,
    MitigationAction,
    ProjectRequirements,
    RiskReport,
    RiskScoreBreakdown,
)
from app.rag.rag_service import RAGService
from app.repositories.risk_repository import RiskRepository
from app.scoring.risk_engine import (
    LiveRuleScorer,
    PreProjectRuleScorer,
    RiskScoringEngine,
)

logger = get_logger(__name__)

_CACHE_TTL = 300  # 5 minutes
_CACHE_KEY = "risk:report:{project_id}:{report_type}"


class RiskService:
    """
    Primary business logic service for risk analysis.
    Orchestrates all subsystems without any infrastructure coupling.
    """

    def __init__(
        self,
        orchestrator: AIOrchestrator,
        rag_service: RAGService,
        ml_predictor: MLPredictor,
        alert_engine: AlertEngine,
        repository: RiskRepository,
        redis: aioredis.Redis,
    ) -> None:
        self._ai = orchestrator
        self._rag = rag_service
        self._ml = ml_predictor
        self._alerts = alert_engine
        self._repo = repository
        self._redis = redis
        self._pre_scorer = PreProjectRuleScorer()
        self._live_scorer = LiveRuleScorer()
        self._engine = RiskScoringEngine()

    # ══════════════════════════════════════════════════════════════════════
    # Pre-Project Analysis
    # ══════════════════════════════════════════════════════════════════════

    async def analyze_pre_project(self, req: ProjectRequirements) -> RiskReport:
        """
        Full pre-project risk analysis pipeline:
          1. Rule-based scoring (fast, synchronous)
          2. ML predictions (feature engineering → model inference)
          3. RAG retrieval (historical context from Qdrant)
          4. AI reasoning (LLM generates explanations + mitigation)
          5. Composite scoring
          6. Persist + cache
        """
        logger.info(
            "Pre-project analysis started",
            project_id=str(req.project_id),
            project_name=req.project_name,
        )

        # Step 1: Rule-based scores
        rule_scores = self._pre_scorer.score(req)

        # Step 2: ML predictions
        ml_result = await self._ml.predict_pre_project(req)

        # Step 3: RAG — find similar historical projects
        query = f"{req.project_name} {req.description} {' '.join(req.required_skills)}"
        historical_context = await self._rag.build_historical_context(query)

        # Step 4: AI reasoning
        ai_result = await self._ai.complete_json(
            PRE_PROJECT_SYSTEM,
            PRE_PROJECT_USER.substitute(
                project_json=req.model_dump_json(indent=2),
                historical_context=historical_context,
            ),
            max_tokens=4096,
        )

        # Step 5: Composite scoring (rules + ML + AI calibration)
        ai_category_scores = ai_result.get("category_scores", {})
        ai_overall = sum(
            v.get("score", 0) for v in ai_category_scores.values()
        ) / max(len(ai_category_scores), 1)

        scores = self._engine.compute_from_rules(
            rule_scores,
            ml_adjustment=ml_result.get("adjustment", 0.0),
            ai_calibration=ai_overall,
        )

        # Step 6: Build structured report
        probabilities = ai_result.get("probabilities", {})
        report = RiskReport(
            project_id=req.project_id,
            report_type="pre_project",
            scores=scores,
            delay_probability=probabilities.get("delay", rule_scores.timeline),
            budget_overrun_probability=probabilities.get(
                "budget_overrun", rule_scores.budget
            ),
            delivery_confidence=1.0 - probabilities.get("delivery_failure", 0.3),
            burnout_probability=probabilities.get("burnout", rule_scores.human),
            executive_summary=ai_result.get("executive_summary", ""),
            root_causes=ai_result.get("root_causes", []),
            predicted_consequences=ai_result.get("predicted_consequences", []),
            mitigation_plan=[
                MitigationAction(**m)
                for m in ai_result.get("mitigation_plan", [])[:5]
            ],
            similar_historical_cases=self._extract_historical_cases(ai_result),
            ml_model_version=ml_result.get("model_version", "1.0.0"),
        )

        # Persist and cache
        await self._repo.save_report(report)
        await self._cache_report(report)

        logger.info(
            "Pre-project analysis complete",
            project_id=str(req.project_id),
            overall_risk=f"{report.scores.overall:.0%}",
            severity=report.scores.severity.value,
        )

        return report

    # ══════════════════════════════════════════════════════════════════════
    # Live Risk Update
    # ══════════════════════════════════════════════════════════════════════

    async def update_live_risk(self, metrics: LiveProjectMetrics) -> RiskReport:
        """
        Live risk update pipeline:
          1. Load previous report for comparison
          2. Rule-based live scoring
          3. ML live predictions
          4. AI live analysis
          5. Alert evaluation
          6. Persist + broadcast
        """
        logger.info(
            "Live risk update",
            project_id=str(metrics.project_id),
        )

        # Load previous report for delta comparison
        previous_report = await self._repo.get_latest_report(metrics.project_id)

        # Rule-based live scoring
        rule_scores = self._live_scorer.score(metrics)

        # ML live predictions
        ml_result = await self._ml.predict_live(metrics)

        # Build previous summary for AI context
        prev_summary = (
            previous_report.executive_summary
            if previous_report
            else "No previous report available."
        )

        # AI live analysis
        ai_result = await self._ai.complete_json(
            LIVE_UPDATE_SYSTEM,
            LIVE_UPDATE_USER.substitute(
                metrics_json=metrics.model_dump_json(indent=2),
                previous_summary=prev_summary,
                baselines=self._build_baselines_context(metrics),
            ),
            max_tokens=4096,
        )

        # Composite scoring
        ai_category_scores = ai_result.get("category_scores", {})
        ai_overall = sum(
            v.get("score", 0) for v in ai_category_scores.values()
        ) / max(len(ai_category_scores), 1)

        scores = self._engine.compute_from_rules(
            rule_scores,
            ml_adjustment=ml_result.get("adjustment", 0.0),
            ai_calibration=ai_overall,
        )

        probabilities = ai_result.get("probabilities", {})
        report = RiskReport(
            project_id=metrics.project_id,
            report_type="live_update",
            scores=scores,
            delay_probability=probabilities.get("delay", rule_scores.timeline),
            budget_overrun_probability=probabilities.get("budget_overrun", rule_scores.budget),
            delivery_confidence=1.0 - probabilities.get("delivery_failure", 0.3),
            burnout_probability=probabilities.get("burnout", rule_scores.human),
            executive_summary=ai_result.get("executive_summary", ""),
            root_causes=ai_result.get("root_causes", []),
            predicted_consequences=ai_result.get("predicted_consequences", []),
            mitigation_plan=[
                MitigationAction(**m)
                for m in ai_result.get("mitigation_plan", [])[:5]
            ],
            similar_historical_cases=[],
            ml_model_version=ml_result.get("model_version", "1.0.0"),
        )

        # Persist snapshot
        await self._repo.save_metrics_snapshot(metrics, scores.overall)
        await self._repo.save_report(report)

        # Evaluate and fire alerts if scores worsened
        if previous_report:
            await self._alerts.evaluate(
                project_id=metrics.project_id,
                current_categories=scores.categories,
                previous_categories=previous_report.scores.categories,
            )

        # Publish risk update to WebSocket subscribers
        await self._publish_update(report)

        return report

    # ══════════════════════════════════════════════════════════════════════
    # Reads
    # ══════════════════════════════════════════════════════════════════════

    async def get_project_snapshot(self, project_id: UUID) -> dict:
        """Get the latest risk state — for WebSocket initial payload."""
        report = await self._repo.get_latest_report(project_id)
        if report is None:
            return {"status": "no_data", "project_id": str(project_id)}
        return report.model_dump()

    async def get_risk_history(
        self, project_id: UUID, limit: int = 30
    ) -> list[dict]:
        """Return time-series risk snapshots for dashboard charts."""
        snapshots = await self._repo.get_metrics_history(project_id, limit=limit)
        return [
            {
                "timestamp": s["snapshot_at"],
                "overall_risk": s["overall_risk_score"],
            }
            for s in snapshots
        ]

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════

    async def _cache_report(self, report: RiskReport) -> None:
        key = _CACHE_KEY.format(
            project_id=str(report.project_id), report_type=report.report_type
        )
        await self._redis.setex(key, _CACHE_TTL, report.model_dump_json())

    async def _publish_update(self, report: RiskReport) -> None:
        channel = f"risk_updates:{report.project_id}"
        await self._redis.publish(
            channel,
            json.dumps(
                {
                    "overall_risk": report.scores.overall,
                    "severity": report.scores.severity.value,
                    "delay_probability": report.delay_probability,
                    "delivery_confidence": report.delivery_confidence,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )

    def _build_baselines_context(self, metrics: LiveProjectMetrics) -> str:
        return (
            f"Sprint velocity baseline: {metrics.planned_velocity} pts/sprint\n"
            f"Current velocity: {metrics.sprint_velocity} pts/sprint\n"
            f"Completion rate: {metrics.sprint_completion_rate:.0%}\n"
            f"Overdue tasks: {metrics.overdue_tasks}/{metrics.total_tasks}"
        )

    def _extract_historical_cases(self, ai_result: dict) -> list[HistoricalSimilarCase]:
        """Parse AI-generated historical case references (if any)."""
        return []  # Extended via RAG retrieval in production
