import os

class Settings:
    DISCORD_CLIENT_ID: str = os.getenv("DISCORD_CLIENT_ID", "")
    DISCORD_CLIENT_SECRET: str = os.getenv("DISCORD_CLIENT_SECRET", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 7
    API_ALLOWED_ORIGINS: str = os.getenv(
        "API_ALLOWED_ORIGINS",
        "https://coc.ixiera.id,https://niki-bot-web.vercel.app,http://localhost:5173"
    )

    @property
    def allowed_origins_list(self):
        return [o.strip() for o in self.API_ALLOWED_ORIGINS.split(",") if o.strip()]

settings = Settings()
