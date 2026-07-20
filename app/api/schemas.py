import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class ScanCreateRequest(BaseModel):
    url: HttpUrl


class RescanRequest(BaseModel):
    project_id: uuid.UUID


class ScanCreateResponse(BaseModel):
    scan_id: uuid.UUID
    project_id: uuid.UUID
    status: str


class HistoryItem(BaseModel):
    scan_id: uuid.UUID
    project_id: uuid.UUID
    url: str
    status: str
    overall_score: float | None
    created_at: datetime
    completed_at: datetime | None


class HistoryResponse(BaseModel):
    scans: list[HistoryItem]
