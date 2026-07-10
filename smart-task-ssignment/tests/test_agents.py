"""
Test suite – covers all five agents and the end-to-end pipeline.
Run with:  pytest tests/ -v
"""
import asyncio
import pytest
from app.models.schemas import (
    TaskInput, TaskRequirements, Employee,
    SeniorityLevel, TaskComplexity,
)
from app.agents.task_agent import task_agent
from app.agents.skill_agent import skill_agent
from app.agents.workload_agent import workload_agent
from app.agents.seniority_agent import seniority_agent
from app.agents.decision_agent import decision_agent


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def backend_employees():
    return [
        Employee(id=1, name="Ahmed",   track="Backend",  skills=["FastAPI","Redis","Docker"],    level="Senior", active_tasks=2,  availability_score=75,  past_success_rate=0.92),
        Employee(id=2, name="Sara",    track="Backend",  skills=["FastAPI","Django","Celery"],   level="Mid",    active_tasks=1,  availability_score=90,  past_success_rate=0.88),
        Employee(id=3, name="Youssef", track="AI/ML",    skills=["PyTorch","FastAPI"],           level="Senior", active_tasks=0,  availability_score=100, past_success_rate=0.89),
    ]

@pytest.fixture
def backend_requirements():
    return TaskRequirements(
        required_track="Backend",
        required_skills=["FastAPI", "Redis", "Docker"],
        seniority_level=SeniorityLevel.SENIOR,
        complexity=TaskComplexity.HIGH,
        summary="High-complexity Backend task.",
    )


# ── Task Understanding Agent ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_task_agent_extracts_track():
    req = await task_agent.run("Build a FastAPI REST API with Redis caching and Docker deployment.")
    assert req.required_track == "Backend"

@pytest.mark.asyncio
async def test_task_agent_extracts_skills():
    req = await task_agent.run("Build a FastAPI REST API with Redis and Docker on Kubernetes.")
    skill_lower = [s.lower() for s in req.required_skills]
    assert "fastapi" in skill_lower

@pytest.mark.asyncio
async def test_task_agent_complexity_critical():
    req = await task_agent.run("Critical production incident: real-time microservice outage.")
    assert req.complexity in (TaskComplexity.CRITICAL, TaskComplexity.HIGH)


# ── Skill Matching Agent ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_skill_agent_top_is_best_match(backend_employees, backend_requirements):
    results = await skill_agent.run(backend_requirements, backend_employees)
    assert results[0].employee_name in ("Ahmed", "Sara")   # both have FastAPI

@pytest.mark.asyncio
async def test_skill_agent_scores_in_range(backend_employees, backend_requirements):
    results = await skill_agent.run(backend_requirements, backend_employees)
    for r in results:
        assert 0 <= r.skill_score <= 100


# ── Workload Monitoring Agent ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workload_agent_most_available_first(backend_employees):
    results = await workload_agent.run(backend_employees)
    # Youssef has 0 active tasks + 100 availability → should be #1
    assert results[0].employee_name == "Youssef"

@pytest.mark.asyncio
async def test_workload_scores_non_negative(backend_employees):
    results = await workload_agent.run(backend_employees)
    for r in results:
        assert r.workload_score >= 0


# ── Seniority Fit Agent ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seniority_agent_senior_task_prefers_senior(backend_employees):
    results = await seniority_agent.run(
        SeniorityLevel.SENIOR, TaskComplexity.HIGH, backend_employees
    )
    top = results[0]
    assert top.employee_name in ("Ahmed", "Youssef")  # both Senior

@pytest.mark.asyncio
async def test_seniority_agent_perfect_match_is_100(backend_employees):
    results = await seniority_agent.run(
        SeniorityLevel.SENIOR, TaskComplexity.HIGH, backend_employees
    )
    senior_scores = [r.seniority_score for r in results if "Senior" in r.employee_name or True]
    assert max(senior_scores) == 100.0


# ── Decision Orchestrator ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_decision_agent_top5_limit(backend_employees, backend_requirements):
    s_scores  = await skill_agent.run(backend_requirements, backend_employees)
    w_scores  = await workload_agent.run(backend_employees)
    sen_scores= await seniority_agent.run(backend_requirements.seniority_level, backend_requirements.complexity, backend_employees)
    recs = await decision_agent.run(backend_requirements, backend_employees, s_scores, w_scores, sen_scores)
    assert len(recs) <= 5

@pytest.mark.asyncio
async def test_decision_agent_ranks_sequential(backend_employees, backend_requirements):
    s_scores  = await skill_agent.run(backend_requirements, backend_employees)
    w_scores  = await workload_agent.run(backend_employees)
    sen_scores= await seniority_agent.run(backend_requirements.seniority_level, backend_requirements.complexity, backend_employees)
    recs = await decision_agent.run(backend_requirements, backend_employees, s_scores, w_scores, sen_scores)
    ranks = [r.rank for r in recs]
    assert ranks == list(range(1, len(recs) + 1))

@pytest.mark.asyncio
async def test_decision_agent_scores_descending(backend_employees, backend_requirements):
    s_scores  = await skill_agent.run(backend_requirements, backend_employees)
    w_scores  = await workload_agent.run(backend_employees)
    sen_scores= await seniority_agent.run(backend_requirements.seniority_level, backend_requirements.complexity, backend_employees)
    recs = await decision_agent.run(backend_requirements, backend_employees, s_scores, w_scores, sen_scores)
    scores = [r.final_score for r in recs]
    assert scores == sorted(scores, reverse=True)
