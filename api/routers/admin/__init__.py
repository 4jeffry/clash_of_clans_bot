from fastapi import APIRouter
from . import dashboard, requests

router = APIRouter()
router.include_router(dashboard.router)
router.include_router(requests.router)
