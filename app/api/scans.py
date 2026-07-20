"""POST /api/scan, POST /api/rescan, GET /api/report/{id}, GET /api/history.

Scans run as an in-process FastAPI BackgroundTask (plan.md's "no queue"
decision) — POST /api/scan and POST /api/rescan return the scan id
immediately with status "pending"; GET /api/report/{id} is polled for the
status/results as the background task moves it through
running -> done/failed.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import (
    HistoryItem,
    HistoryResponse,
    RescanRequest,
    ScanCreateRequest,
    ScanCreateResponse,
)
from app.db.session import AsyncSessionLocal, get_db
from app.models import HistoricalScore, Project, Recommendation, Report, Scan
from app.pipeline.runner import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


async def _execute_scan(scan_id: uuid.UUID, url: str) -> None:
    """The background task: owns its own DB session, independent of the
    request that queued it (the request's session may already be closed by
    the time this runs)."""
    async with AsyncSessionLocal() as session:
        scan = await session.get(Scan, scan_id)
        scan.status = "running"
        scan.started_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        result = await run_pipeline(url)
    except Exception as e:
        logger.exception("Pipeline failed for scan %s (%s)", scan_id, url)
        async with AsyncSessionLocal() as session:
            scan = await session.get(Scan, scan_id)
            scan.status = "failed"
            scan.error_message = str(e)
            scan.completed_at = datetime.now(timezone.utc)
            await session.commit()
        return

    async with AsyncSessionLocal() as session:
        scan = await session.get(Scan, scan_id)
        scan.status = "done"
        scan.completed_at = datetime.now(timezone.utc)

        report = Report(
            scan_id=scan.id,
            profile_json=result.profile.to_dict(),
            score_json=result.score.to_dict(),
            findings_json=[c.to_dict() for c in result.checks],
            narrative_json=result.reasoning.report.model_dump(),
            citation_issues_json=[issue.__dict__ for issue in result.reasoning.citation_issues],
        )
        session.add(report)
        await session.flush()

        for index, rec in enumerate(result.recommendations):
            session.add(Recommendation(report_id=report.id, sort_order=index, **rec.to_dict()))

        session.add(
            HistoricalScore(project_id=scan.project_id, scan_id=scan.id, overall_score=result.score.overall_score)
        )

        await session.commit()


@router.post("/api/scan", response_model=ScanCreateResponse, status_code=202)
async def create_scan(
    payload: ScanCreateRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)
) -> ScanCreateResponse:
    url = str(payload.url)

    existing = await db.execute(select(Project).where(Project.url == url))
    project = existing.scalar_one_or_none()
    if project is None:
        project = Project(url=url)
        db.add(project)
        await db.flush()

    scan = Scan(project_id=project.id, requested_url=url, status="pending")
    db.add(scan)
    await db.commit()

    background_tasks.add_task(_execute_scan, scan.id, url)

    return ScanCreateResponse(scan_id=scan.id, project_id=project.id, status=scan.status)


@router.post("/api/rescan", response_model=ScanCreateResponse, status_code=202)
async def rescan(
    payload: RescanRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)
) -> ScanCreateResponse:
    project = await db.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    scan = Scan(project_id=project.id, requested_url=project.url, status="pending")
    db.add(scan)
    await db.commit()

    background_tasks.add_task(_execute_scan, scan.id, project.url)

    return ScanCreateResponse(scan_id=scan.id, project_id=project.id, status=scan.status)


@router.get("/api/report/{scan_id}")
async def get_report(scan_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(Scan)
        .where(Scan.id == scan_id)
        .options(selectinload(Scan.report).selectinload(Report.recommendations))
    )
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")

    payload: dict = {
        "scan_id": scan.id,
        "project_id": scan.project_id,
        "url": scan.requested_url,
        "status": scan.status,
        "error_message": scan.error_message,
        "created_at": scan.created_at,
        "started_at": scan.started_at,
        "completed_at": scan.completed_at,
        "report": None,
    }

    if scan.report is not None:
        r = scan.report
        payload["report"] = {
            "profile": r.profile_json,
            "score": r.score_json,
            "findings": r.findings_json,
            "narrative": r.narrative_json,
            "citation_issues": r.citation_issues_json,
            "recommendations": [
                {
                    "check_id": rec.check_id,
                    "dimension": rec.dimension,
                    "severity": rec.severity,
                    "issue": rec.issue,
                    "impact": rec.impact,
                    "recommendation": rec.recommendation,
                }
                for rec in r.recommendations
            ],
        }

    return payload


@router.get("/api/history", response_model=HistoryResponse)
async def get_history(
    scan_ids: list[uuid.UUID] = Query(default=[]),
    project_ids: list[uuid.UUID] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    """No auth in v1 — the frontend tracks "its own" scan/project ids in
    localStorage and passes them back here to hydrate a personal-feeling
    history list without real ownership."""
    if not scan_ids and not project_ids:
        return HistoryResponse(scans=[])

    conditions = []
    if scan_ids:
        conditions.append(Scan.id.in_(scan_ids))
    if project_ids:
        conditions.append(Scan.project_id.in_(project_ids))

    stmt = (
        select(Scan, Project.url, HistoricalScore.overall_score)
        .join(Project, Scan.project_id == Project.id)
        .outerjoin(HistoricalScore, HistoricalScore.scan_id == Scan.id)
        .where(or_(*conditions))
        .order_by(Scan.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    return HistoryResponse(
        scans=[
            HistoryItem(
                scan_id=scan.id,
                project_id=scan.project_id,
                url=url,
                status=scan.status,
                overall_score=overall_score,
                created_at=scan.created_at,
                completed_at=scan.completed_at,
            )
            for scan, url, overall_score in rows
        ]
    )
