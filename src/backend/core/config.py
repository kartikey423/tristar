"""Application settings loaded from environment variables.

F-009 FIX: PURCHASE_TRIGGER_ENABLED and PURCHASE_TRIGGER_PILOT_MEMBERS added
for safe phased rollout without code changes.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── External APIs ──────────────────────────────────────────────────────────
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    WEATHER_API_KEY: str = ""
    NOTIFICATION_PROVIDER_URL: str = "http://localhost:9000/notify"

    # ── Hub API ────────────────────────────────────────────────────────────────
    HUB_API_URL: str = "http://localhost:8000/api/hub"

    # ── Hub Redis store ────────────────────────────────────────────────────────
    HUB_REDIS_ENABLED: bool = False
    REDIS_URL: str = "redis://localhost:6379"

    # ── Audit log ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///tristar.db"

    # ── Designer API (used by Scout for internal service calls) ───────────────
    DESIGNER_API_URL: str = "http://localhost:8000"

    # ── Inventory data ─────────────────────────────────────────────────────────
    INVENTORY_FILE_PATH: str = "data/inventory.csv"

    # ── JWT / Auth ─────────────────────────────────────────────────────────────
    JWT_SECRET: str = "dev-secret-change-in-prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 1
    SERVICE_JWT_EXPIRY_HOURS: int = 24

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    # ── Claude API cache ───────────────────────────────────────────────────────
    CACHE_TTL_SECONDS: int = 300  # 5 minutes

    # ── Purchase-trigger thresholds ────────────────────────────────────────────
    PURCHASE_TRIGGER_SCORE_THRESHOLD: float = 70.0
    PURCHASE_TRIGGER_RATE_LIMIT_HOURS: int = 6
    OFFER_VALID_UNTIL_HOURS: int = 4  # purchase-triggered offers expire after 4h
    OFFER_EXPIRY_SWEEP_SECONDS: int = 300  # F-004: background sweep every 5 min

    # ── Delivery constraints ────────────────────────────────────────────────────
    QUIET_HOURS_START: int = 22  # 10pm
    QUIET_HOURS_END: int = 8  # 8am
    DEDUP_WINDOW_HOURS: int = 24
    HIGH_VALUE_PURCHASE_THRESHOLD: float = 100.0  # bypass 24h dedup if amount > $100

    # ── Scout match endpoint feature flag (new Hub-matching flow) ───────────────
    SCOUT_MATCH_ENABLED: bool = True
    # Max active Hub offers to score per match request (F-005 design review fix)
    SCOUT_CANDIDATE_CAP: int = 5

    # ── F-009: Feature flag + pilot rollout ─────────────────────────────────────
    PURCHASE_TRIGGER_ENABLED: bool = False
    # Comma-separated member IDs allowed in pilot; empty = all members (when enabled)
    PURCHASE_TRIGGER_PILOT_MEMBERS: str = ""

    # ── Webhook security ───────────────────────────────────────────────────────
    SCOUT_WEBHOOK_SECRET: str = "dev-webhook-secret"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    @property
    def pilot_member_ids(self) -> set[str]:
        """Parse PURCHASE_TRIGGER_PILOT_MEMBERS into a set of member IDs."""
        if not self.PURCHASE_TRIGGER_PILOT_MEMBERS.strip():
            return set()
        return {m.strip() for m in self.PURCHASE_TRIGGER_PILOT_MEMBERS.split(",") if m.strip()}


settings = Settings()
