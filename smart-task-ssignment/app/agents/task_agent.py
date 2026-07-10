"""
Agent 1 – Task Understanding Agent
===================================
Receives raw task text and extracts structured requirements.
Uses keyword / rule-based NLP (fast, no external API needed).
Pluggable: swap `_extract_requirements` with an LLM call for richer output.
"""
import asyncio
import re
import time
import logging
from typing import List

from app.models.schemas import TaskRequirements, SeniorityLevel, TaskComplexity

logger = logging.getLogger(__name__)

# ── Vocabulary maps ───────────────────────────────────────────────────────────

TRACK_KEYWORDS: dict[str, List[str]] = {
    "Backend":  ["fastapi", "django", "flask", "api", "rest", "graphql", "database",
                 "sql", "postgresql", "mysql", "redis", "celery", "microservice",
                 "backend", "server", "endpoint", "bug", "fix", "login", "auth",
                 "sheet", "excel", "data", "report", "script", "automation"],
    "Frontend": ["react", "vue", "angular", "typescript", "javascript", "css",
                 "html", "tailwind", "ui", "ux", "frontend", "web", "browser",
                 "nextjs", "nuxt", "component", "page", "form", "button", "design"],
    "DevOps":   ["docker", "kubernetes", "k8s", "ci/cd", "terraform", "aws",
                 "azure", "gcp", "pipeline", "deploy", "devops", "infra",
                 "cloud", "container", "monitoring", "helm", "railway", "hosting"],
    "AI/ML":    ["machine learning", "deep learning", "neural", "model", "training",
                 "inference", "pytorch", "tensorflow", "langchain", "llm", "nlp",
                 "computer vision", "opencv", "mlflow", "ai", "ml", "scikit", "gemini"],
}

SKILL_KEYWORDS: List[str] = [
    "fastapi", "django", "flask", "redis", "docker", "kubernetes", "postgresql",
    "mysql", "celery", "react", "vue", "angular", "typescript", "tailwindcss",
    "nextjs", "nuxt", "graphql", "terraform", "aws", "azure", "gcp", "pytorch",
    "tensorflow", "langchain", "opencv", "mlflow", "scikit-learn",
    "pandas", "sqlalchemy", "alembic", "ci/cd", "restapi", "websocket",
    "python", "javascript", "html", "css", "excel", "sql",
]

SENIORITY_PATTERNS: dict[str, List[str]] = {
    "Lead":   ["architect", "lead", "principal", "staff", "head of", "director"],
    "Senior": ["senior", "complex", "critical", "high-stakes", "production",
               "scalable", "advanced", "expert"],
    "Mid":    ["mid", "intermediate", "moderate", "standard"],
    "Junior": ["junior", "simple", "basic", "beginner", "entry", "easy"],
}

COMPLEXITY_PATTERNS: dict[str, List[str]] = {
    "Critical": ["critical", "urgent", "mission-critical", "p0", "outage", "incident"],
    "High":     ["high", "complex", "distributed", "scalable", "microservice",
                 "real-time", "performance", "security", "large-scale"],
    "Medium":   ["medium", "moderate", "standard", "typical", "regular"],
    "Low":      ["low", "simple", "quick", "small", "trivial", "easy"],
}


# ── Main agent ────────────────────────────────────────────────────────────────

class TaskUnderstandingAgent:
    """Synchronous-core, async-wrapped task analysis agent."""

    name = "Task Understanding Agent"

    async def run(self, task_description: str) -> TaskRequirements:
        """Analyse the task and return structured requirements (async)."""
        logger.info(f"[{self.name}] Starting analysis…")
        # Simulate brief processing latency (real LLM call would take longer)
        await asyncio.sleep(0.3)
        result = self._extract_requirements(task_description)
        logger.info(f"[{self.name}] Done – track={result.required_track}, "
                    f"complexity={result.complexity}")
        return result

    # ── Core logic ────────────────────────────────────────────────────────────

    def _extract_requirements(self, text: str) -> TaskRequirements:
        lower = text.lower()

        track        = self._detect_track(lower)
        skills       = self._detect_skills(lower)
        seniority    = self._detect_seniority(lower)
        complexity   = self._detect_complexity(lower)
        summary      = self._build_summary(text, track, skills, seniority, complexity)

        return TaskRequirements(
            required_track   = track,
            required_skills  = skills,
            seniority_level  = seniority,
            complexity       = complexity,
            summary          = summary,
        )

    def _detect_track(self, text: str) -> str:
        scores: dict[str, int] = {t: 0 for t in TRACK_KEYWORDS}
        for track, keywords in TRACK_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    scores[track] += 1
        best = max(scores, key=lambda t: scores[t])
        return best if scores[best] > 0 else "Backend"   # default

    def _detect_skills(self, text: str) -> List[str]:
        found: List[str] = []
        for skill in SKILL_KEYWORDS:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                found.append(skill.capitalize() if '-' not in skill else skill)
        # Deduplicate, keep order
        seen = set()
        unique = []
        for s in found:
            key = s.lower()
            if key not in seen:
                seen.add(key)
                unique.append(s)
        # No fake fallback skill here on purpose: the previous "Python" default
        # was silently injected whenever nothing in SKILL_KEYWORDS matched, but
        # no seed employee actually lists "Python" as a skill — so skill_agent's
        # Jaccard similarity came out 0 for every employee on every such task,
        # making the final ranking (which weighs skill match 40%) collapse to
        # whatever track/workload/seniority defaults applied, regardless of what
        # was actually typed. An honest empty list lets skill_agent apply a
        # neutral score instead of a systematically wrong zero.
        return unique

    def _detect_seniority(self, text: str) -> SeniorityLevel:
        for level in ["Lead", "Senior", "Mid", "Junior"]:
            for kw in SENIORITY_PATTERNS[level]:
                if kw in text:
                    return SeniorityLevel(level)
        return SeniorityLevel.SENIOR  # default assumption

    def _detect_complexity(self, text: str) -> TaskComplexity:
        for level in ["Critical", "High", "Medium", "Low"]:
            for kw in COMPLEXITY_PATTERNS[level]:
                if kw in text:
                    return TaskComplexity(level)
        return TaskComplexity.MEDIUM  # default


    def _build_summary(self, original: str, track: str, skills: List[str],
                       seniority: SeniorityLevel, complexity: TaskComplexity) -> str:
        skill_str = ", ".join(skills[:4]) if skills else "general"
        return (
            f"{complexity.value}-complexity {track} task requiring {seniority.value}-level "
            f"expertise in: {skill_str}."
        )


# Module-level singleton
task_agent = TaskUnderstandingAgent()
