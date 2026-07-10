"""
End-to-end pipeline test: Data Collector (mocked backend) -> Metrics Engine
-> Risk Engine -> AI Estimators (mocked LLM) -> Report Builder.
Nothing here touches a real network.
"""

import pytest
import httpx
from unittest.mock import patch

from app.data_collector.collector_factory import get_project_context
from app.metrics.metrics_engine import compute_all_metrics
from app.risk_engine.rules import calculate_timeline_risk, calculate_resource_risk
from app.risk_engine.aggregator import aggregate_overall_risk
from tests.mocks.mock_backend import build_mock_backend_transport
from tests.mocks.mock_llm_providers import MockLLMProvider


@pytest.mark.asyncio
async def test_full_pipeline_with_unified_backend():
    transport = build_mock_backend_transport(mode="unified")
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-backend") as client:
        context = await get_project_context("proj-1", client)

    assert context.collection_mode == "unified"
    assert context.data_completeness == 1.0

    metrics = compute_all_metrics(context)
    timeline_risk = calculate_timeline_risk(metrics["raw"])
    resource_risk = calculate_resource_risk(metrics["raw"])
    overall = aggregate_overall_risk([timeline_risk, resource_risk])

    assert 0 <= overall.score <= 100


@pytest.mark.asyncio
async def test_full_pipeline_falls_back_to_multi_endpoint_mode():
    transport = build_mock_backend_transport(mode="multi_endpoint")
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-backend") as client:
        context = await get_project_context("proj-1", client)

    assert context.collection_mode == "multi_endpoint"


@pytest.mark.asyncio
async def test_ai_estimated_metrics_degrade_gracefully_when_llm_fails():
    from app.ai_estimators.estimated_metrics import generate_ai_estimated_metrics
    from app.schemas.context_schema import ProjectContext, ProjectInfo

    context = ProjectContext(
        project=ProjectInfo(project_id="p1", project_name="Test"),
        collection_mode="unified",
    )

    with patch("app.ai_estimators.estimated_metrics.generate_with_fallback") as mock_gen:
        from app.exceptions.llm import AllLLMProvidersExhaustedError
        mock_gen.side_effect = AllLLMProvidersExhaustedError(["gemini", "groq"])

        ai_metrics, budget_risk, narrative, recs = await generate_ai_estimated_metrics(context, {})

    assert all(m.confidence <= 0.3 for m in ai_metrics)
    assert budget_risk.source == "ai_estimated"
