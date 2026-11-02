from __future__ import annotations

import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ml02_user:ml02_dev_password@localhost:5433/ml02_demo",
)
APP_ENV = os.getenv("APP_ENV", "development")
ENABLE_MOCK_FRESHNESS = os.getenv("ML02_ENABLE_MOCK_FRESHNESS", "true").lower() in {
    "1", "true", "yes", "on"
}
FRESHNESS_HALF_LIFE_DAYS = float(os.getenv("ML02_FRESHNESS_HALF_LIFE_DAYS", "7"))
MODEL_VERSION_OVERRIDE = os.getenv("ML02_MODEL_VERSION")
