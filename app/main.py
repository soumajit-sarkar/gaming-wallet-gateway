from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description=(
        "Public reference implementation of a gaming wallet gateway. "
        "Financial operations are processed atomically against the relational database."
    ),
    version=settings.app_version,
    debug=settings.debug,
)
app.include_router(api_router)
