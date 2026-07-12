import pytest
from unittest.mock import patch

from app.ai.enrichment import AIEnrichmentLayer
from app.context.builder import ContextBuilder
from app.models.raw import RawEmployee, RawTask, RawTeamSnapshot
from tests.mocks.mock_llm_provider import MockLLMProvider


def _context():
    snapshot = RawTeamSnapshot(
        scope_type="project", scope_id="p1", scope_name="Test",
        employees=[RawEmployee(id="e1", first_name="Ahmed", last_name="Nasser")],
        tasks=[RawTask(id="t1", title="Fix bug", status="in_progress", priority=8, assigned_to_user_id="e1")],
    )
    return ContextBuilder().build(snapshot, source="demo")


@pytest.mark.asyncio
async def test_enrichment_skipped_when_no_provider_configured():
    with patch("app.ai.factory.get_ordered_providers", return_value=[]):
        ctx = await AIEnrichmentLayer().enrich(_context())
    assert ctx.employees[0].ai_enrichment is None
    assert any("skipped" in w for w in ctx.data_quality_warnings)


@pytest.mark.asyncio
async def test_enrichment_applies_successful_response():
    response = {
        "employees": {
            "e1": {
                "task_complexity_counts": {"low": 0, "medium": 0, "high": 1, "critical": 0},
                "estimated_task_difficulty": {"value": "hard", "confidence": 0.8, "reason": "r"},
                "estimated_work_complexity": {"value": "high", "confidence": 0.8, "reason": "r"},
                "burnout_indicator": {"value": "moderate", "confidence": 0.7, "reason": "r"},
                "productivity_trend": {"value": "stable", "confidence": 0.7, "reason": "r"},
                "focus_capacity": {"value": "medium", "confidence": 0.7, "reason": "r"},
                "context_switching_cost": {"value": "low", "confidence": 0.7, "reason": "r"},
                "collaboration_difficulty": {"value": "low", "confidence": 0.7, "reason": "r"},
                "estimated_priority_weight": {"value": 70.0, "confidence": 0.7, "reason": "r"},
                "availability_score": {"value": 30.0, "confidence": 0.7, "reason": "r"},
                "narrative": "Ahmed is on track.",
            }
        }
    }
    with patch("app.ai.factory.get_ordered_providers", return_value=[MockLLMProvider(response)]):
        ctx = await AIEnrichmentLayer().enrich(_context())
    emp = ctx.employees[0]
    assert emp.ai_enrichment is not None
    assert emp.ai_enrichment["narrative"] == "Ahmed is on track."
    assert emp.availability_score == 30.0
    assert emp.task_complexity_distribution.high == 1


@pytest.mark.asyncio
async def test_enrichment_degrades_gracefully_on_provider_failure():
    with patch("app.ai.factory.get_ordered_providers", return_value=[MockLLMProvider(should_fail=True)]):
        ctx = await AIEnrichmentLayer().enrich(_context())
    assert ctx.employees[0].ai_enrichment is None
    assert any("failed" in w for w in ctx.data_quality_warnings)


@pytest.mark.asyncio
async def test_enrichment_degrades_gracefully_on_malformed_json():
    class BadProvider(MockLLMProvider):
        async def complete(self, system_prompt, user_prompt):
            return "not json at all"

    with patch("app.ai.factory.get_ordered_providers", return_value=[BadProvider()]):
        ctx = await AIEnrichmentLayer().enrich(_context())
    assert ctx.employees[0].ai_enrichment is None
    assert ctx.data_quality_warnings  # some warning recorded, pipeline did not crash
