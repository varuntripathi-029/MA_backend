"""GET /api/methodology — reads DIMENSION_WEIGHTS directly from the Scoring
Engine (app/pipeline/scoring.py) rather than restating the numbers, so the
published methodology page and the number the engine actually computes can
never drift apart."""

from fastapi import APIRouter

from app.pipeline.scoring import DIMENSION_WEIGHTS

router = APIRouter()


@router.get("/api/methodology")
def get_methodology() -> dict:
    return {
        "dimensions": [
            {"dimension": dim, "weight": w.weight, "rationale": w.rationale}
            for dim, w in DIMENSION_WEIGHTS.items()
        ],
    }
