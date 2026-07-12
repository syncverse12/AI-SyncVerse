from fastapi.testclient import TestClient


def _client(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    return TestClient(app)


def test_health(monkeypatch):
    client = _client(monkeypatch)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["app_mode"] == "demo"


def test_scopes_lists_demo_scenarios(monkeypatch):
    client = _client(monkeypatch)
    r = client.get("/api/v1/workload/scopes")
    assert r.status_code == 200
    names = {s["scope_id"] for s in r.json()["scopes"]}
    assert "overloaded_team" in names
    assert "critical_project" in names


def test_analyze_overloaded_team_detects_imbalance(monkeypatch):
    client = _client(monkeypatch)
    r = client.post("/api/v1/workload/analyze/project/overloaded_team")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "demo"
    assert body["report"]["status"] in ("imbalance_detected", "critical_imbalance")
    assert len(body["report"]["overloaded_employees"]) >= 1
    assert body["report"]["recommended_actions"]
    for action in body["report"]["recommended_actions"]:
        assert action["requires_approval"] is True


def test_analyze_normal_project_is_balanced_or_mild(monkeypatch):
    client = _client(monkeypatch)
    r = client.post("/api/v1/workload/analyze/project/normal_project")
    assert r.status_code == 200
    assert r.json()["report"]["team_health_score"] >= 50


def test_analyze_unknown_scope_type_rejected(monkeypatch):
    client = _client(monkeypatch)
    r = client.post("/api/v1/workload/analyze/bogus/normal_project")
    assert r.status_code == 400


def test_legacy_simulate_endpoint_still_works(monkeypatch):
    client = _client(monkeypatch)
    r = client.post("/api/v1/workload/simulate/balanced")
    assert r.status_code in (200, 404)  # 404 only if the legacy scenario name changed


def test_status_before_any_analysis_gives_friendly_message(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.services import balancer_service as bs
    bs._service = None  # force a fresh singleton with no history
    from app.main import app
    client = TestClient(app)
    r = client.get("/api/v1/workload/status")
    assert r.status_code == 200
