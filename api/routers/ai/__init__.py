from fastapi import APIRouter
from . import audit, war_room, history

router = APIRouter()
router.include_router(audit.router)
router.include_router(war_room.router)
router.include_router(history.router)
