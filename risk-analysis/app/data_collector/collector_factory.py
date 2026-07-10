"""
Entry point the Orchestrator actually calls. Hides the Mode 1 / Mode 2
decision so `risk_report_service.py` just does:

    context = await get_project_context(project_id, http_client)

and never needs to know which strategy fetched the data.
"""

import logging
import httpx

from app.schemas.context_schema import ProjectContext
from app.data_collector.unified_mode import UnifiedModeCollector
from app.data_collector.multi_endpoint_mode import MultiEndpointModeCollector
from app.data_collector.demo_mode import DemoModeCollector
from app.core.config import get_settings
from app.exceptions.collector import (
    UnifiedEndpointNotSupportedError,
    BackendUnavailableError,
    ProjectNotFoundError,
)

logger = logging.getLogger(__name__)


async def get_project_context(project_id: str, http_client: httpx.AsyncClient) -> ProjectContext:
    if get_settings().demo_mode:
        logger.info(
            "demo_mode_active_skipping_backend",
            extra={"event": "demo_mode_active_skipping_backend", "project_id": project_id},
        )
        return await DemoModeCollector().collect(project_id)

    unified = UnifiedModeCollector(http_client)

    try:
        return await unified.collect(project_id)
    except UnifiedEndpointNotSupportedError:
        # Expected for backends without the aggregated endpoint — not an error.
        logger.info(
            "falling_back_to_multi_endpoint_mode",
            extra={"event": "falling_back_to_multi_endpoint_mode", "project_id": project_id},
        )
    except BackendUnavailableError as exc:
        # Unified endpoint exists conceptually but the call itself failed —
        # still worth trying Mode 2 in case only that one route is down.
        logger.warning(
            "unified_mode_failed_trying_fallback",
            extra={"event": "unified_mode_failed_trying_fallback", "project_id": project_id, "reason": exc.reason},
        )
    except ProjectNotFoundError:
        raise  # No point falling back — the project genuinely doesn't exist.

    multi_endpoint = MultiEndpointModeCollector(http_client)
    return await multi_endpoint.collect(project_id)
