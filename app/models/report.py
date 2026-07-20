import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Report(Base):
    """A completed scan's results: the Machine Profile (Module 5), the score
    (Module 7), the raw rule-check findings (Module 4), and Module 6's
    narrative plus its citation/polarity issue list. The issue list is kept
    for debugging visibility even though the UI doesn't prominently surface
    it (per explicit instruction)."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), unique=True, nullable=False)
    profile_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    score_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    findings_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    narrative_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    citation_issues_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scan: Mapped["Scan"] = relationship(back_populates="report")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="Recommendation.sort_order"
    )
