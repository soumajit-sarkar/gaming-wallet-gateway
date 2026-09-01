from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title="Gaming Wallet Gateway",
    description="Sanitized FastAPI reference implementation of a high-throughput gaming wallet gateway.",
    version=settings.app_version
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}