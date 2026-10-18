from fastapi import APIRouter
from . import dashboard, requests, broadcast, stats, analytics

router = APIRouter()
router.include_router(stats.router)
router.include_router(dashboard.router)
router.include_router(requests.router)
router.include_router(broadcast.router)
router.include_router(analytics.router)
