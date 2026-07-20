from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.methodology import router as methodology_router
from app.api.scans import router as scans_router
from app.core.config import settings

app = FastAPI(title="MX_rating API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(methodology_router)
app.include_router(scans_router)


@app.get("/health")
def health():
    return {"status": "ok"}
