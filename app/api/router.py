from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.players import router as players_router
from app.api.transactions import router as transactions_router
from app.api.wallets import router as wallets_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(players_router, prefix="/api/v1")
api_router.include_router(wallets_router, prefix="/api/v1")
api_router.include_router(transactions_router, prefix="/api/v1")
