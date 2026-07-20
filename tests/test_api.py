"""FastAPI TestClient happy-path tests for the four scan/report/history/
rescan endpoints. The pipeline itself is mocked (run_pipeline is patched)
so these tests don't touch the network or Groq — they exercise the API
contract and DB writes, not the pipeline logic (that's covered by
test_pipeline_integration.py and the Module 4/6/7/8 unit tests)."""

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from app.api import scans as scans_module
from app.main import app
from app.db.session import get_db
from app.pipeline.reasoning import GroundedClaim, ReasoningReport, ReasoningResult
from app.pipeline.runner import PipelineResult
from app.pipeline.scoring import DimensionScore, ScoreResult

from .fixtures import GOOD_HTML, make_crawl_result


async def _fake_run_pipeline(url: str) -> PipelineResult:
    from app.pipeline.cleaner import clean_html
    from app.pipeline.extractor import extract_features
    from app.pipeline.profile import build_profile
    from app.pipeline.recommendations import build_recommendations
    from app.pipeline.rules.engine import run_checks

    crawl = make_crawl_result(requested_url=url)
    crawl.rendered_html = GOOD_HTML
    features = extract_features(clean_html(GOOD_HTML))
    checks = run_checks(features, crawl)
    profile = build_profile(features, crawl, checks)
    score = ScoreResult(overall_score=88.5, dimensions=[DimensionScore("trust", 1.0, 0.2, 0.2)])
    recs = build_recommendations(checks)
    reasoning = ReasoningResult(
        report=ReasoningReport(
            purpose="test purpose",
            target_users=["testers"],
            agent_strengths=[GroundedClaim(text="good title", citation="content.title")],
            agent_weaknesses=[],
            missing_information=[],
            confidence=0.9,
            recommendations=[],
        ),
        citation_issues=[],
        model="fake-model",
    )
    return PipelineResult(
        crawl=crawl, features=features, checks=checks, profile=profile, score=score,
        recommendations=recs, reasoning=reasoning,
    )


@pytest.fixture
def client(test_sessionmaker, monkeypatch):
    @asynccontextmanager
    async def fake_resilient_session():
        async with test_sessionmaker() as session:
            yield session

    monkeypatch.setattr(scans_module, "resilient_session", fake_resilient_session)
    monkeypatch.setattr(scans_module, "run_pipeline", _fake_run_pipeline)

    async def override_get_db():
        async with test_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def test_scan_report_roundtrip(client):
    create_resp = client.post("/api/scan", json={"url": "https://acme.example/"})
    assert create_resp.status_code == 202
    body = create_resp.json()
    assert body["status"] == "pending"
    scan_id = body["scan_id"]
    project_id = body["project_id"]

    # TestClient runs the background task synchronously within the request
    # lifecycle, so the scan is already "done" by the time this returns.
    report_resp = client.get(f"/api/report/{scan_id}")
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["status"] == "done"
    assert report["project_id"] == project_id
    assert report["report"]["score"]["overall_score"] == 88.5
    assert report["report"]["narrative"]["purpose"] == "test purpose"
    assert len(report["report"]["recommendations"]) >= 0


def test_report_404_for_unknown_scan(client):
    resp = client.get("/api/report/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_history_by_project_id(client):
    create_resp = client.post("/api/scan", json={"url": "https://acme.example/"})
    project_id = create_resp.json()["project_id"]

    history_resp = client.get(f"/api/history?project_ids={project_id}")
    assert history_resp.status_code == 200
    scans = history_resp.json()["scans"]
    assert len(scans) == 1
    assert scans[0]["project_id"] == project_id
    assert scans[0]["status"] == "done"


def test_history_empty_when_no_ids_given(client):
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert resp.json() == {"scans": []}


def test_rescan_reuses_project(client):
    create_resp = client.post("/api/scan", json={"url": "https://acme.example/"})
    project_id = create_resp.json()["project_id"]
    first_scan_id = create_resp.json()["scan_id"]

    rescan_resp = client.post("/api/rescan", json={"project_id": project_id})
    assert rescan_resp.status_code == 202
    body = rescan_resp.json()
    assert body["project_id"] == project_id
    assert body["scan_id"] != first_scan_id

    history_resp = client.get(f"/api/history?project_ids={project_id}")
    assert len(history_resp.json()["scans"]) == 2


def test_rescan_unknown_project_404s(client):
    resp = client.post("/api/rescan", json={"project_id": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 404


def test_methodology_endpoint(client):
    resp = client.get("/api/methodology")
    assert resp.status_code == 200
    dims = resp.json()["dimensions"]
    assert len(dims) == 6
    assert abs(sum(d["weight"] for d in dims) - 1.0) < 1e-9
