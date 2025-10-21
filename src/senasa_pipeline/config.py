from __future__ import annotations
from dataclasses import dataclass
import os
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

@dataclass(frozen=True)
class Settings:
    afip_cuit: str = os.getenv("AFIP_CUIT", "")
    http_timeout: float = float(os.getenv("HTTP_TIMEOUT", "45"))
    session_ttl_hours: int = int(os.getenv("SESSION_TTL_HOURS", "12"))

settings = Settings()
