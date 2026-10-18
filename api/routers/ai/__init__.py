from fastapi import APIRouter
from . import audit, war_room, history, war_report, cwl_roster

router = APIRouter()
router.include_router(audit.router)
router.include_router(war_room.router)
router.include_router(history.router)
router.include_router(war_report.router)
router.include_router(cwl_roster.router)
