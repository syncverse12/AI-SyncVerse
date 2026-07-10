"""
Interface every Data Collector implementation must satisfy.

The Orchestrator depends on this abstraction only — never on
UnifiedModeCollector or MultiEndpointModeCollector directly — so swapping
strategies (or adding a Mode 3 later) never touches the Metrics Engine.
"""

from abc import ABC, abstractmethod
from app.schemas.context_schema import ProjectContext


class DataCollector(ABC):
    @abstractmethod
    async def collect(self, project_id: str) -> ProjectContext:
        """
        Fetch and normalize everything the Metrics Engine needs for one
        project. Must always return a ProjectContext — never raise for
        *partial* data (that's encoded via missing_sources /
        data_completeness). Only raise for total failure
        (ProjectNotFoundError, BackendUnavailableError).
        """
        raise NotImplementedError
