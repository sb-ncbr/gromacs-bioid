"""Identifier resolution module.

Provides base classes and utilities for resolving molecular identifiers
from signatures (e.g., SMILES, InChIKey) to database identifiers.
"""

from .base import IdentifierResolver, IdentifierResolutionError
from .cache_manager import ResolverCache
from .registry import IdentifierRegistry, get_default_resolvers
from .resolution_manager import IdentifierResolutionManager

__all__ = [
    "IdentifierResolver",
    "IdentifierRegistry",
    "IdentifierResolutionManager",
    "ResolverCache",
    "IdentifierResolutionError",
    "get_default_resolvers",
]
