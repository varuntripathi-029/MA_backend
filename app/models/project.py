import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Project(Base):
    """A tracked site (identified by URL). No owning Users record in v1 —
    anonymous scans only (plan.md Data model note)."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scans: Mapped[list["Scan"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    historical_scores: Mapped[list["HistoricalScore"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
