"""
Agent 2 – Skill Matching Agent
================================
Compares task required_skills with each employee's skill set.
Uses token-level Jaccard + alias normalisation for fuzzy matching.
Pluggable: replace `_similarity` with embedding cosine similarity for production.
"""
import asyncio
import logging
from typing import List, Dict

from app.models.schemas import TaskRequirements, Employee, SkillMatchResult

logger = logging.getLogger(__name__)

# ── Skill alias / synonym table ───────────────────────────────────────────────
ALIASES: Dict[str, str] = {
    "fastapi": "fastapi", "fast api": "fastapi",
    "postgres": "postgresql", "pg": "postgresql",
    "k8s": "kubernetes",
    "tailwind": "tailwindcss",
    "scikit": "scikit-learn", "sklearn": "scikit-learn",
    "nextjs": "nextjs", "next.js": "nextjs",
    "nuxtjs": "nuxt", "nuxt.js": "nuxt",
    "typescript": "typescript", "ts": "typescript",
    "javascript": "javascript", "js": "javascript",
    "pytorch": "pytorch", "torch": "pytorch",
    "tensorflow": "tensorflow", "tf": "tensorflow",
    "langchain": "langchain",
    "openai": "openai",
    "rest": "restapi", "rest api": "restapi",
}


def _normalise(skill: str) -> str:
    return ALIASES.get(skill.lower().strip(), skill.lower().strip())


class SkillMatchingAgent:
    """Computes skill-match scores for all employees against the task requirements."""

    name = "Skill Matching Agent"

    async def run(
        self,
        requirements: TaskRequirements,
        employees: List[Employee],
    ) -> List[SkillMatchResult]:
        logger.info(f"[{self.name}] Matching {len(employees)} employees…")
        await asyncio.sleep(0.2)   # simulate brief async work

        results: List[SkillMatchResult] = []
        task_skills_norm = {_normalise(s) for s in requirements.required_skills}

        # If the Task Understanding Agent couldn't extract any concrete skill
        # from the description (e.g. a task described in plain, non-technical
        # language), there is nothing meaningful to compute a Jaccard score
        # against. Returning 0 for every employee in that case previously made
        # the 40%-weighted skill component silently decide the whole ranking
        # by elimination — a neutral 50 lets workload/seniority/performance
        # actually differentiate candidates instead.
        no_requirements_detected = not task_skills_norm

        for emp in employees:
            emp_skills_norm = {_normalise(s) for s in emp.skills}

            matched   = task_skills_norm & emp_skills_norm
            missing   = task_skills_norm - emp_skills_norm
            union     = task_skills_norm | emp_skills_norm

            if no_requirements_detected:
                score = 50.0
            else:
                # Jaccard similarity (0–1), boosted by track match
                jaccard = len(matched) / len(union) if union else 0.0
                track_boost = 1.15 if emp.track.lower() == requirements.required_track.lower() else 1.0
                raw_score = min(jaccard * track_boost, 1.0)
                # Scale to 0–100
                score = round(raw_score * 100, 2)

            results.append(SkillMatchResult(
                employee_id    = emp.id,
                employee_name  = emp.name,
                skill_score    = score,
                matched_skills = list(matched),
                missing_skills = list(missing),
            ))

        results.sort(key=lambda r: r.skill_score, reverse=True)
        logger.info(f"[{self.name}] Done – top skill score: {results[0].skill_score if results else 0}")
        return results


skill_agent = SkillMatchingAgent()
