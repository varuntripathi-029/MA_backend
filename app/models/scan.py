import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

SCAN_STATUSES = ("pending", "running", "done", "failed")


class Scan(Base):
    """One pipeline run (Modules 1-8) against a project's URL."""

    __tablename__ = "scans"
    __table_args__ = (CheckConstraint("status in ('pending','running','done','failed')", name="ck_scans_status"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    requested_url: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="scans")
    report: Mapped["Report | None"] = relationship(
        back_populates="scan", uselist=False, cascade="all, delete-orphan"
    )
    historical_score: Mapped["HistoricalScore | None"] = relationship(
        back_populates="scan", uselist=False, cascade="all, delete-orphan"
    )
