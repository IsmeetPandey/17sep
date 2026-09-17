from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: str = os.getenv("INVOICEGUARD_DB", "./data/invoiceguard.sqlite3")
    api_key: str | None = os.getenv("INVOICEGUARD_API_KEY")
    environment: str = os.getenv("INVOICEGUARD_ENV", "development")
    price_tolerance_pct: float = float(os.getenv("INVOICEGUARD_PRICE_TOLERANCE_PCT", "2.0"))


settings = Settings()
