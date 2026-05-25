"""
Agent 4 – Seniority Fit Agent
================================
Scores how well an employee's seniority level matches the
required complexity of the task.

Scoring matrix (row = employee level, col = required level):
          Junior  Mid   Senior  Lead
Junior      100    60    30      10
Mid          70   100    70      40
Senior       50    80   100      80
Lead         30    60    90     100

The agent penalises over- and under-qualification differently:
  - Over-qualified (e.g., Lead on Junior task): mild penalty – they can still do it.
  - Under-qualified (e.g., Junior on Critical task): heavy penalty.
"""
import asyncio
import logging
from typing import List

from app.models.schemas import Employee, SeniorityScore, SeniorityLevel, TaskComplexity

logger = logging.getLogger(__name__)

# ── Scoring matrices ──────────────────────────────────────────────────────────

# Maps (employee_level, required_level) → raw score (0–100)
SENIORITY_MATRIX: dict[tuple[str, str], float] = {
    ("Junior", "Junior"): 100, ("Junior", "Mid"): 60,  ("Junior", "Senior"): 30, ("Junior", "Lead"): 10,
    ("Mid",    "Junior"): 70,  ("Mid",    "Mid"): 100, ("Mid",    "Senior"): 70, ("Mid",    "Lead"): 40,
    ("Senior", "Junior"): 50,  ("Senior", "Mid"): 80,  ("Senior", "Senior"): 100,("Senior", "Lead"): 80,
    ("Lead",   "Junior"): 30,  ("Lead",   "Mid"): 60,  ("Lead",   "Senior"): 90, ("Lead",   "Lead"): 100,
}

# Complexity → required seniority level (used when task_requirements.seniority_level
# is not explicit but complexity IS)
COMPLEXITY_TO_SENIORITY: dict[str, str] = {
    "Low":      "Junior",
    "Medium":   "Mid",
    "High":     "Senior",
    "Critical": "Lead",
}


class SeniorityFitAgent:
    """Scores each employee's seniority fit against task requirements."""

    name = "Seniority Fit Agent"

    async def run(
        self,
        required_seniority: SeniorityLevel,
        required_complexity: TaskComplexity,
        employees: List[Employee],
    ) -> List[SeniorityScore]:
        logger.info(f"[{self.name}] Scoring {len(employees)} employees – "
                    f"required={required_seniority}, complexity={required_complexity}…")
        await asyncio.sleep(0.1)

        # Derive the "effective" required level from both signals
        effective_level = self._effective_level(required_seniority, required_complexity)

        results: List[SeniorityScore] = []
        for emp in employees:
            score = SENIORITY_MATRIX.get((emp.level, effective_level), 50.0)
            results.append(SeniorityScore(
                employee_id   = emp.id,
                employee_name = emp.name,
                seniority_score = score,
            ))

        results.sort(key=lambda r: r.seniority_score, reverse=True)
        logger.info(f"[{self.name}] Done – effective required level: {effective_level}")
        return results

    def _effective_level(
        self,
        required_seniority: SeniorityLevel,
        required_complexity: TaskComplexity,
    ) -> str:
        """
        When both seniority and complexity are specified, take the higher of the two
        (complexity drives the floor, explicit seniority is the ceiling).
        """
        seniority_rank = {"Junior": 0, "Mid": 1, "Senior": 2, "Lead": 3}
        seniority_from_complexity = COMPLEXITY_TO_SENIORITY[required_complexity.value]

        r1 = seniority_rank.get(str(required_seniority), 2)
        r2 = seniority_rank.get(seniority_from_complexity, 2)
        idx = max(r1, r2)
        return ["Junior", "Mid", "Senior", "Lead"][idx]


seniority_agent = SeniorityFitAgent()
