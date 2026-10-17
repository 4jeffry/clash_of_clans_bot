import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api")

app = FastAPI(title="Niki API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "service": "Niki API"}

@app.get("/health")
def health():
    return {"status": "healthy"}


from api.routers import auth, clan
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(clan.router, prefix="/clan", tags=["clan"])
