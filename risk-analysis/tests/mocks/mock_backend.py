"""
Mock backend server (httpx MockTransport) used by integration tests, so no
real network call ever leaves the test suite.
"""

import httpx


def build_mock_backend_transport(mode: str = "unified"):
    """
    mode="unified": /risk-context exists and returns full data.
    mode="multi_endpoint": /risk-context 404s, individual endpoints work.
    mode="degraded": individual endpoints partially fail (for graceful-degradation tests).
    """

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path.endswith("/risk-context"):
            if mode == "unified":
                return httpx.Response(200, json={
                    "project": {"project_name": "Demo Project", "budget": 10000, "priority": "High", "status": "active"},
                    "tasks": [], "timeline": [], "milestones": [], "risks": [],
                    "time_logs": [], "team_members": [], "meetings": [],
                })
            return httpx.Response(404)

        if path.endswith("/timelogs") and mode == "degraded":
            return httpx.Response(500)

        if "/projects/" in path and path.count("/") == 2:  # GET /projects/{id}
            return httpx.Response(200, json={"project_name": "Demo Project", "budget": 10000, "priority": "High", "status": "active"})

        # every other individual endpoint (tasks, timeline, milestones, risks, team-members, team-meetings)
        return httpx.Response(200, json=[])

    return httpx.MockTransport(handler)
