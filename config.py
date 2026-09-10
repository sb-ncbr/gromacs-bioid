"""Configuration for Validation API."""

import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://validation:validation-password-change-me@validation-postgres.ceitec-biodata-ns.svc.cluster.local:5432/bat3_validation"
)
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    "redis://bat3-redis.ceitec-biodata-ns.svc.cluster.local:6379/0"
)
MDDBR_API_BASE = os.getenv(
    "MDDBR_API_BASE",
    "https://mdposit.mddbr.eu/api/rest/v1"
)
