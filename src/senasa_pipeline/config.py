from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env if present
load_dotenv()


@dataclass(frozen=True)
class Settings:
    afip_cuit: str = os.getenv("AFIP_CUIT", "")
    afip_password: str = os.getenv("AFIP_PASSWORD", "")
    http_timeout: float = float(os.getenv("HTTP_TIMEOUT", "45"))
    session_ttl_hours: int = int(os.getenv("SESSION_TTL_HOURS", "12"))


settings = Settings()
