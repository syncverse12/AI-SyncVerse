"""Mock LLM provider used in integration tests — never calls a real API."""

import json
from app.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    name = "mock"

    def __init__(self, should_fail: bool = False):
        self._should_fail = should_fail

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self._should_fail:
            from app.exceptions.llm import LLMProviderUnavailableError
            raise LLMProviderUnavailableError(self.name, "simulated failure")

        return json.dumps({
            "ai_estimated_metrics": [
                {"name": "Team Pressure", "value": "Medium", "confidence": 0.7, "reason": "test"},
                {"name": "Schedule Stability", "value": "High", "confidence": 0.75, "reason": "test"},
                {"name": "Delivery Confidence", "value": "Medium", "confidence": 0.6, "reason": "test"},
                {"name": "Budget Pressure", "value": "Low", "confidence": 0.65, "reason": "test"},
            ],
            "narrative": "Project is broadly on track with moderate workload pressure.",
            "recommendations": [
                {"priority": "Medium", "related_risk": "Resource Risk", "action": "Monitor workload distribution next sprint."}
            ],
        })
