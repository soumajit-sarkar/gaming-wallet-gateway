from fastapi import FastAPI
from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title="Gaming Wallet Gateway",
    description="Sanitized FastAPI reference implementation of a high-throughput gaming wallet gateway.",
    version=settings.app_version
)


app.include_router(api_router)