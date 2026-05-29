"""Name-based identifier resolver using JSON databases."""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import TYPE_CHECKING

from ..base import IdentifierResolver, IdentifierResolutionError

if TYPE_CHECKING:
    from ...config.loader import RunConfig

logger = logging.getLogger("identifier")


# Module-level cache for JSON databases
_db_cache: dict[str, dict] = {}


class NameDBSource(Enum):
    """Source database for name resolution."""
    CCD = "ccd"
    MAPS = "maps"
    MANUAL = "manual"


class NameResolver(IdentifierResolver):
    """Resolver for name signatures using JSON database lookups.

    Looks up names in a JSON database and returns the associated InChIKey.
    """

    name = "name"
    identifier_type = "INCHIKEY"
    accepted_signatures = ["name"]

    def __init__(self, config: RunConfig, db_source: NameDBSource) -> None:
        """Initialize name resolver.

        Args:
            config: RunConfig instance containing names configuration.
            db_source: Source database (CCD, MAPS, or MANUAL).
        """
        super().__init__(config)
        self.db_source = db_source
        # Set specific name based on source
        self.name = f"name_{db_source.value}"
        
        # Get DB path from config
        if db_source == NameDBSource.CCD:
            self.db_path = config.names.ccd_db
        elif db_source == NameDBSource.MAPS:
            self.db_path = config.names.maps_db
        else:  # MANUAL
            self.db_path = config.names.manual_db

    def _load_db(self, path: str) -> dict:
        """Load JSON database from file or cache.

        Args:
            path: Path to JSON database file.

        Returns:
            Dict mapping names to InChIKeys.
        """
        global _db_cache
        if path not in _db_cache:
            with open(path, "r") as fd:
                _db_cache[path] = json.load(fd)
        return _db_cache[path]

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature is applicable.

        Args:
            signature: The name string.

        Returns:
            True (all name signatures are applicable).
        """
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve name to InChIKey via database lookup.

        Args:
            signature: Name string to look up.
            working_directory: Unused.

        Returns:
            List containing InChIKey if found, empty list otherwise.
        """
        try:
            db = self._load_db(self.db_path)
            inchikey = db.get(signature)
            if inchikey:
                return [str(inchikey)]
            return []
        except FileNotFoundError:
            logger.warning(f"[Identifier] Name database not found: {self.db_path}")
            return []
        except json.JSONDecodeError as exc:
            raise IdentifierResolutionError(f"[Identifier] Invalid JSON in name database {self.db_path}: {exc}")
        except Exception as exc:
            raise IdentifierResolutionError(f"[Identifier] Name lookup failed: {exc}")

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve name to similar identifiers.

        Not implemented for name lookups. Returns empty list.

        Args:
            signature: Name string.
            working_directory: Unused.

        Returns:
            Empty list.
        """
        return []


class NameResolverCCD(NameResolver):
    """Name resolver using CCD database."""

    def __init__(self, config: RunConfig) -> None:
        """Initialize CCD name resolver.

        Args:
            config: RunConfig instance containing names configuration.
        """
        super().__init__(config, NameDBSource.CCD)


class NameResolverMAPS(NameResolver):
    """Name resolver using LIPID MAPS database."""

    def __init__(self, config: RunConfig) -> None:
        """Initialize MAPS name resolver.

        Args:
            config: RunConfig instance containing names configuration.
        """
        super().__init__(config, NameDBSource.MAPS)


class NameResolverMANUAL(NameResolver):
    """Name resolver using manual database."""

    def __init__(self, config: RunConfig) -> None:
        """Initialize manual name resolver.

        Args:
            config: RunConfig instance containing names configuration.
        """
        super().__init__(config, NameDBSource.MANUAL)
