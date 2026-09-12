"""Configuration module for BAT3 pipeline."""

from .loader import (
    RunConfig,
    ConfigSection,
    LoaderConfig,
    ExecutorConfig,
    TaskTimeoutConfig,
    SignaturesConfig,
    IdentifiersConfig,
    BlastConfig,
    ChemblConfig,
    IdsmConfig,
    PubchemConfig,
    AlphafindConfig,
    VerificationConfig,
    load_config_from_path,
    merge_with_dict,
)

__all__ = [
    "RunConfig",
    "ConfigSection",
    "LoaderConfig",
    "ExecutorConfig",
    "TaskTimeoutConfig",
    "SignaturesConfig",
    "IdentifiersConfig",
    "BlastConfig",
    "ChemblConfig",
    "IdsmConfig",
    "PubchemConfig",
    "AlphafindConfig",
    "VerificationConfig",
    "load_config_from_path",
    "merge_with_dict",
]

# Re-export for compatibility
from src_new.config.loader import DATABASE_URL, CELERY_BROKER_URL, MDDBR_API_BASE
