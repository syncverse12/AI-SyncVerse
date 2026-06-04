"""
Autonomous Alert Engine — detects, classifies, deduplicates, and dispatches alerts.

Flow:
  Risk score computed
    → AlertEngine.evaluate(project_id, current_scores, previous_scores)
        → detect anomalies
        → check cooldown (Redis)
        → check dedup (Redis)
        → generate AI insight
        → persist alert (Postgres)
        → publish to Redis Pub/Sub (→ WebSocket broadcast)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import (
    AlertPayload,
    AlertStatus,
    CategoryRiskScore,
    RiskCategory,
    RiskSeverity,
)

logger = get_logger(__name__)

# Redis key patterns
_COOLDOWN_KEY = "alert:cooldown:{project_id}:{category}"
_DEDUP_KEY = "alert:dedup:{project_id}:{category}:{severity}"


class AlertEngine:
    """
    Autonomous risk alert detection and dispatch engine.
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        orchestrator: Any,  # AIOrchestrator — avoid circular import
        alert_repo: Any,    # AlertRepository
    ) -> None:
        self._redis = redis
        self._orchestrator = orchestrator
        self._alert_repo = alert_repo

    async def evaluate(
        self,
        project_id: UUID,
        current_categories: list[CategoryRiskScore],
        previous_categories: list[CategoryRiskScore],
    ) -> list[AlertPayload]:
        """
        Compare current vs previous category scores.
        Returns a list of alerts that were fired (after dedup/cooldown).
        """
        fired_alerts: list[AlertPayload] = []
        prev_map = {c.category: c for c in previous_categories}

        for current in current_categories:
            prev = prev_map.get(current.category)
            if prev is None:
                continue

            delta = current.score - prev.score

            # Only alert on meaningful increases
            if delta < 0.05:
                continue

            # Must cross a severity threshold
            if not self._crosses_threshold(current.score):
                continue

            # Cooldown check — don't spam alerts for the same category
            if await self._is_in_cooldown(project_id, current.category):
                logger.debug(
                    "Alert suppressed by cooldown",
                    project_id=str(project_id),
                    category=current.category.value,
                )
                continue

            # Deduplication — same severity already active?
            if await self._is_duplicate(project_id, current.category, current.severity):
                logger.debug(
                    "Alert suppressed by dedup",
                    project_id=str(project_id),
                    category=current.category.value,
                )
                continue

            # Generate AI insight for this anomaly
            ai_insight = await self._generate_insight(current, prev, delta)

            alert = AlertPayload(
                project_id=project_id,
                severity=current.severity,
                risk_category=current.category,
                title=self._build_title(current, delta),
                message=self._build_message(current, prev, delta),
                root_cause="; ".join(current.contributing_factors[:3]),
                ai_insight=ai_insight,
                recommended_action=self._recommend_action(current),
                previous_risk_score=round(prev.score, 4),
                current_risk_score=round(current.score, 4),
                delta=round(delta, 4),
                escalation_level=self._escalation_level(current.severity),
                notify_roles=self._notify_roles(current),
            )

            # Persist alert
            await self._alert_repo.create(alert)

            # Set cooldown and dedup markers
            await self._set_cooldown(project_id, current.category)
            await self._set_dedup(project_id, current.category, current.severity)

            # Publish to Redis Pub/Sub for WebSocket broadcast
            await self._publish(alert)

            fired_alerts.append(alert)
            logger.info(
                "Alert fired",
                alert_id=str(alert.alert_id),
                severity=alert.severity.value,
                category=alert.risk_category.value,
                delta=alert.delta,
            )

        return fired_alerts

    # ── Threshold logic ──────────────────────────────────────────────────────

    def _crosses_threshold(self, score: float) -> bool:
        return score >= settings.alert_threshold_low

    # ── Cooldown ─────────────────────────────────────────────────────────────

    async def _is_in_cooldown(self, project_id: UUID, category: RiskCategory) -> bool:
        key = _COOLDOWN_KEY.format(
            project_id=str(project_id), category=category.value
        )
        return bool(await self._redis.exists(key))

    async def _set_cooldown(self, project_id: UUID, category: RiskCategory) -> None:
        key = _COOLDOWN_KEY.format(
            project_id=str(project_id), category=category.value
        )
        await self._redis.setex(key, settings.alert_cooldown_seconds, "1")

    # ── Deduplication ────────────────────────────────────────────────────────

    async def _is_duplicate(
        self,
        project_id: UUID,
        category: RiskCategory,
        severity: RiskSeverity,
    ) -> bool:
        key = _DEDUP_KEY.format(
            project_id=str(project_id),
            category=category.value,
            severity=severity.value,
        )
        return bool(await self._redis.exists(key))

    async def _set_dedup(
        self,
        project_id: UUID,
        category: RiskCategory,
        severity: RiskSeverity,
    ) -> None:
        key = _DEDUP_KEY.format(
            project_id=str(project_id),
            category=category.value,
            severity=severity.value,
        )
        # Dedup window: 4x the cooldown
        await self._redis.setex(key, settings.alert_cooldown_seconds * 4, "1")

    # ── AI insight generation ────────────────────────────────────────────────

    async def _generate_insight(
        self,
        current: CategoryRiskScore,
        prev: CategoryRiskScore,
        delta: float,
    ) -> str:
        from app.ai.prompts.risk_prompts import ALERT_INSIGHT_SYSTEM, ALERT_INSIGHT_USER

        try:
            prompt = ALERT_INSIGHT_USER.substitute(
                category=current.category.value,
                previous_score=f"{prev.score:.0%}",
                current_score=f"{current.score:.0%}",
                delta=f"+{delta:.0%}",
                factors="; ".join(current.contributing_factors),
            )
            result = await self._orchestrator.complete_json(
                ALERT_INSIGHT_SYSTEM, prompt, max_tokens=256
            )
            return result.get("ai_insight", "Risk threshold exceeded — review recommended.")
        except Exception as exc:
            logger.warning("AI insight generation failed", error=str(exc))
            return "Risk level increased significantly — immediate review required."

    # ── Publishing ───────────────────────────────────────────────────────────

    async def _publish(self, alert: AlertPayload) -> None:
        channel = f"alerts:{alert.project_id}"
        payload = alert.model_dump_json()
        await self._redis.publish(channel, payload)
        logger.debug("Alert published to Redis", channel=channel)

    # ── Message builders ─────────────────────────────────────────────────────

    def _build_title(self, current: CategoryRiskScore, delta: float) -> str:
        return (
            f"{current.severity.value} {current.category.value.title()} Risk: "
            f"{current.score:.0%} (+{delta:.0%})"
        )

    def _build_message(
        self,
        current: CategoryRiskScore,
        prev: CategoryRiskScore,
        delta: float,
    ) -> str:
        factors_str = "; ".join(current.contributing_factors[:2])
        return (
            f"{current.category.value.title()} risk increased from "
            f"{prev.score:.0%} to {current.score:.0%} (+{delta:.0%}). "
            f"Contributing factors: {factors_str}."
        )

    def _recommend_action(self, current: CategoryRiskScore) -> str:
        actions = {
            RiskCategory.TIMELINE: "Run emergency sprint re-scoping session with PM and tech lead.",
            RiskCategory.HUMAN: "Reduce workload, redistribute tasks, and assess burnout indicators.",
            RiskCategory.TECHNICAL: "Schedule technical debt review and unblock critical PRs.",
            RiskCategory.CLIENT: "Schedule client alignment call within 24 hours.",
            RiskCategory.DELIVERY: "Review sprint completion blockers with the entire team.",
            RiskCategory.BUDGET: "Flag to finance team and review scope for cuts.",
            RiskCategory.INFRASTRUCTURE: "Escalate infrastructure issues to DevOps team immediately.",
        }
        return actions.get(current.category, "Immediate risk review required.")

    def _escalation_level(self, severity: RiskSeverity) -> int:
        return {
            RiskSeverity.LOW: 1,
            RiskSeverity.MEDIUM: 1,
            RiskSeverity.HIGH: 2,
            RiskSeverity.CRITICAL: 3,
        }[severity]

    def _notify_roles(self, current: CategoryRiskScore) -> list[str]:
        base = ["project_manager"]
        if current.severity in (RiskSeverity.HIGH, RiskSeverity.CRITICAL):
            base.extend(["engineering_lead", "product_owner"])
        if current.severity == RiskSeverity.CRITICAL:
            base.extend(["cto", "account_manager"])
        return base


# Type annotation fix
from typing import Any  # noqa: E402 (circular import guard)
