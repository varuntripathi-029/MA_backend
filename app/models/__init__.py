"""Import every model module here so Base.metadata is complete for Alembic
autogenerate and for create_all() in tests, regardless of which module a
caller happens to import first."""

from app.models.historical_score import HistoricalScore
from app.models.project import Project
from app.models.recommendation import Recommendation
from app.models.report import Report
from app.models.scan import Scan

__all__ = ["Project", "Scan", "Report", "Recommendation", "HistoricalScore"]
