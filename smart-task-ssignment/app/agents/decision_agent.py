"""
Agent 5 – Decision Orchestrator Agent
========================================
Combines outputs from all four upstream agents into a final ranked list.

Scoring weights:
  Skill Match        → 40 %
  Workload Balance   → 20 %
  Seniority Fit      → 20 %
  Past Performance   → 20 %
"""
import asyncio
import logging
from typing import List, Dict

from app.models.schemas import (
    Employee,
    TaskRequirements,
    SkillMatchResult,
    WorkloadScore,
    SeniorityScore,
    EmployeeRecommendation,
)

logger = logging.getLogger(__name__)

# ── Weight constants ──────────────────────────────────────────────────────────
W_SKILL       = 0.40
W_WORKLOAD    = 0.20
W_SENIORITY   = 0.20
W_PERFORMANCE = 0.20

TOP_N = 5


class DecisionOrchestratorAgent:
    """Merges agent outputs and produces the final ranked recommendations."""

    name = "Decision Orchestrator Agent"

    async def run(
        self,
        requirements: TaskRequirements,
        employees: List[Employee],
        skill_scores: List[SkillMatchResult],
        workload_scores: List[WorkloadScore],
        seniority_scores: List[SeniorityScore],
    ) -> List[EmployeeRecommendation]:
        logger.info(f"[{self.name}] Merging scores for {len(employees)} employees…")
        await asyncio.sleep(0.1)

        # Index scores by employee_id for O(1) lookup
        skill_map:     Dict[int, SkillMatchResult] = {s.employee_id: s for s in skill_scores}
        workload_map:  Dict[int, WorkloadScore]    = {s.employee_id: s for s in workload_scores}
        seniority_map: Dict[int, SeniorityScore]   = {s.employee_id: s for s in seniority_scores}

        scored: List[EmployeeRecommendation] = []

        for emp in employees:
            skill_r     = skill_map.get(emp.id)
            workload_r  = workload_map.get(emp.id)
            seniority_r = seniority_map.get(emp.id)

            # Graceful fallback if an agent missed this employee
            skill_score       = skill_r.skill_score       if skill_r     else 0.0
            workload_score    = workload_r.workload_score  if workload_r  else 0.0
            seniority_score   = seniority_r.seniority_score if seniority_r else 0.0
            performance_score = emp.past_success_rate * 100  # normalise to 0–100

            final_score = round(
                skill_score       * W_SKILL       +
                workload_score    * W_WORKLOAD     +
                seniority_score   * W_SENIORITY    +
                performance_score * W_PERFORMANCE,
                2,
            )

            reason = self._build_reason(
                emp, requirements,
                skill_score, workload_score, seniority_score, performance_score,
                skill_r.matched_skills if skill_r else [],
            )

            scored.append(EmployeeRecommendation(
                rank             = 0,   # set below
                employee_id      = emp.id,
                name             = emp.name,
                track            = emp.track,
                level            = emp.level,
                final_score      = final_score,
                skill_score      = round(skill_score, 2),
                workload_score   = round(workload_score, 2),
                seniority_score  = round(seniority_score, 2),
                performance_score= round(performance_score, 2),
                reason           = reason,
                matched_skills   = skill_r.matched_skills if skill_r else [],
            ))

        # Sort descending and assign ranks
        scored.sort(key=lambda r: r.final_score, reverse=True)
        top = scored[:TOP_N]
        for i, rec in enumerate(top, start=1):
            rec.rank = i

        logger.info(
            f"[{self.name}] Done – #1: {top[0].name} ({top[0].final_score}) "
            if top else f"[{self.name}] No candidates found."
        )
        return top

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_reason(
        self,
        emp: Employee,
        req: TaskRequirements,
        skill: float,
        workload: float,
        seniority: float,
        performance: float,
        matched: List[str],
    ) -> str:
        parts: List[str] = []

        if skill >= 70:
            parts.append(f"strong skill match ({', '.join(matched[:3]) or 'general'})")
        elif skill >= 40:
            parts.append("moderate skill overlap")
        else:
            parts.append("limited skill match")

        if workload >= 70:
            parts.append("low current workload")
        elif workload >= 40:
            parts.append("manageable workload")
        else:
            parts.append("high existing workload")

        if seniority >= 80:
            parts.append(f"ideal seniority level ({emp.level})")
        elif seniority >= 50:
            parts.append(f"acceptable seniority ({emp.level})")
        else:
            parts.append(f"seniority mismatch ({emp.level})")

        if performance >= 90:
            parts.append(f"excellent track record ({emp.past_success_rate:.0%})")
        elif performance >= 75:
            parts.append(f"solid track record ({emp.past_success_rate:.0%})")

        return "; ".join(parts).capitalize() + "."


decision_agent = DecisionOrchestratorAgent()
