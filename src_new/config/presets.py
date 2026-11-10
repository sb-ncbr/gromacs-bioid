"""Per-run configuration a user may change, and the run presets.

The web UI, the REST API and the MCP server let a user adjust a run's
configuration. Only the fields listed in ``TUNABLE`` may differ from the
server's config.ini: which databases are searched, the match thresholds and
the verification window. Everything else (executables, database paths, URLs,
threads, the parallel executor flags) is deployment configuration; an
override of it is rejected unless it repeats the server's own value (older
clients post the whole default config back).
"""
from __future__ import annotations

import dataclasses
from typing import Any

from .loader import RunConfig

# Fields not offered in the identifiers section although they are booleans:
# overwrite_existing has no meaning for a fresh run, formula_chembl is the
# PubChem-outage fallback.
_IDENTIFIERS_EXCLUDED = {"overwrite_existing", "formula_chembl"}

# Numeric tunables: (minimum, maximum), both inclusive.
_NUMBER_BOUNDS: dict[str, dict[str, tuple[float, float]]] = {
    "loader": {
        "element_mass_tolerance": (0.0, 1.0),
        "bond_guess_vdw_factor": (0.1, 2.0),
    },
    "signatures": {
        "smiles_maximum_number_of_atoms": (1, 1000),
    },
    "blast": {
        "exact_match_max_evalue": (0.0, 10.0),
        "exact_match_min_bits": (0, 10000),
        "exact_match_min_identity_p": (0.0, 1.0),
        "exact_match_min_query_cov_p": (0.0, 1.0),
        "similarity_match_max_evalue": (0.0, 10.0),
        "similarity_match_min_bits": (0, 10000),
        "similarity_match_min_identity_p": (0.0, 1.0),
        "similarity_match_min_query_cov_p": (0.0, 1.0),
    },
    "chembl": {"similarity_threshold": (0, 100)},
    "idsm": {"similarity_threshold": (0, 100)},
    "pubchem": {"similarity_threshold": (0, 100)},
    "verification": {
        "verify_top_n": (1, 200),
        "verify_top_n_supplementary": (0, 100),
        "similarity_top_n": (1, 50),
        "resolver_weight": (0.0, 100.0),
        "similarity_weight": (0.0, 100.0),
        "annotation_weight": (0.0, 100.0),
        "tm_score_threshold": (0.0, 1.0),
        "min_final_confidence": (0.0, 100.0),
    },
}

_BOOLEAN_TUNABLES: dict[str, set[str]] = {
    "loader": {
        "tpr_resid_from_one", "guess_missing_elements", "guess_missing_masses",
        "guess_missing_names", "guess_missing_bonds", "quick_structure_search",
        "unwrap_periodic_boundaries",
    },
    "signatures": {
        "fasta_map_determine_sequence_partial_mode",
        "fasta_map_determine_sequence_strict_mode",
        "enhanced_nucleic_acid_recognition",
    },
    "pdb": {"rcsb_include_mixed_complexes"},
    "verification": {"enable_annotation_quality", "annotation_live_fetch"},
}


def _identifier_toggles() -> set[str]:
    return {
        f.name for f in dataclasses.fields(RunConfig().identifiers)
        if f.type in (bool, "bool") and f.name not in _IDENTIFIERS_EXCLUDED
    }


#: section -> fields a run may change
TUNABLE: dict[str, frozenset[str]] = {
    section: frozenset(_BOOLEAN_TUNABLES.get(section, set()) | set(_NUMBER_BOUNDS.get(section, {})))
    for section in set(_BOOLEAN_TUNABLES) | set(_NUMBER_BOUNDS)
}
TUNABLE["identifiers"] = frozenset(_identifier_toggles())

# Order of the sections in GET /runs/config/options (the UI renders it as is).
_SECTION_ORDER = ["identifiers", "verification", "blast", "chembl", "idsm", "pubchem",
                  "pdb", "signatures", "loader"]

# Searches that dominate a run's time: the NCBI nr/nt databases (hundreds of
# GB read from NFS), UniRef50, and the structure searches (AlphaFind and the
# RCSB structure search are remote, Foldseek is a local subprocess).
_SLOW_SEARCHES = [
    "blast_nr_protein", "blast_nt", "blast_core_nt", "blast_uniref50",
    "alphafind_struct", "foldseek_3di", "foldseek_pdb", "pdb_struct_protein",
    "pdb_struct_nucleotide",
]


def _both(names: list[str], value: bool) -> dict[str, bool]:
    return {k: value for n in names for k in (n, f"{n}_similarity")}


#: Presets offered on run submission. ``overrides`` are applied on top of the
#: server defaults; every key must be in TUNABLE (checked by the tests).
PRESETS: list[dict[str, Any]] = [
    {
        "id": "balanced",
        "title": "Balanced",
        "description": "Recommended. Every database, exact and similar matches.",
        "details": "The server defaults.",
        "icon": "scale",
        "overrides": {},
    },
    {
        "id": "quick",
        "title": "Quick look",
        "description": "Skips the slowest searches. Minutes rather than up to an hour.",
        "details": "No NCBI nr/nt, UniRef50 or structure searches (AlphaFind, Foldseek, "
                   "RCSB); 30 candidates verified per molecule, no live annotation fetch.",
        "icon": "zap",
        "overrides": {
            "identifiers": _both(_SLOW_SEARCHES, False),
            "verification": {
                "verify_top_n": 30,
                "verify_top_n_supplementary": 10,
                "similarity_top_n": 5,
                "annotation_live_fetch": False,
            },
        },
    },
    {
        "id": "exact",
        "title": "Exact matches",
        "description": "Identical database entries only: no homologues or analogues.",
        "details": "Every similarity search is off; each database is searched for "
                   "identical entries only.",
        "icon": "target",
        "overrides": {
            "identifiers": {f"{n}_similarity": False for n in sorted(TUNABLE["identifiers"])
                            if not n.endswith("_similarity") and f"{n}_similarity" in TUNABLE["identifiers"]},
        },
    },
    {
        "id": "deep",
        "title": "Deep search",
        "description": "More candidates verified, more similar matches. Slowest.",
        "details": "150 candidates verified per molecule (60 more from the supplementary "
                   "databases), 20 similar matches kept, mixed protein/nucleic-acid PDB "
                   "complexes searched.",
        "icon": "telescope",
        "overrides": {
            "verification": {
                "verify_top_n": 150,
                "verify_top_n_supplementary": 60,
                "similarity_top_n": 20,
            },
            "pdb": {"rcsb_include_mixed_complexes": True},
        },
    },
]

PRESETS_BY_ID = {p["id"]: p for p in PRESETS}


class ConfigOverrideError(ValueError):
    """An override names an unknown field, a non-tunable field or a bad value."""


def tunable_config(config: RunConfig) -> dict[str, dict[str, Any]]:
    """The tunable part of ``config`` as {section: {field: value}}."""
    full = config.to_dict()
    out: dict[str, dict[str, Any]] = {}
    for section in _SECTION_ORDER:
        fields = TUNABLE.get(section, frozenset())
        values = full.get(section) or {}
        out[section] = {k: v for k, v in values.items() if k in fields}
    return out


def _check_value(section: str, field: str, value: Any, current: Any) -> None:
    path = f"{section}.{field}"
    if isinstance(current, bool):
        if not isinstance(value, bool):
            raise ConfigOverrideError(f"{path} must be true or false")
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigOverrideError(f"{path} must be a number")
    if isinstance(current, int) and not float(value).is_integer():
        raise ConfigOverrideError(f"{path} must be a whole number")
    lo, hi = _NUMBER_BOUNDS[section][field]
    if not lo <= value <= hi:
        raise ConfigOverrideError(f"{path} must be between {lo} and {hi}")


def checked_overrides(nested: Any, base: RunConfig) -> dict[str, dict[str, Any]]:
    """Validate user overrides against ``base`` (the server defaults).

    Returns the overrides to apply: the tunable fields that differ from
    ``base``, with values coerced to the field's type. A non-tunable field is
    accepted only when it equals the server value, and then dropped. Raises
    ConfigOverrideError otherwise.
    """
    if not isinstance(nested, dict):
        raise ConfigOverrideError("config must be an object of sections")
    full = base.to_dict()
    out: dict[str, dict[str, Any]] = {}
    for section, fields in nested.items():
        if section.startswith("_"):
            continue
        if section not in full or not isinstance(full[section], dict):
            raise ConfigOverrideError(f"Unknown config section: {section}")
        if not isinstance(fields, dict):
            raise ConfigOverrideError(f"Config section {section} must be an object")
        for field, value in fields.items():
            if field.startswith("_"):
                continue
            if field not in full[section]:
                raise ConfigOverrideError(f"Unknown config field: {section}.{field}")
            current = full[section][field]
            if value == current and type(value) is type(current):
                continue
            if field not in TUNABLE.get(section, frozenset()):
                raise ConfigOverrideError(f"{section}.{field} cannot be changed per run")
            _check_value(section, field, value, current)
            if isinstance(current, int) and not isinstance(current, bool):
                value = int(value)
            elif isinstance(current, float):
                value = float(value)
            out.setdefault(section, {})[field] = value
    return out


def overrides_from_ini(text: str, base: RunConfig) -> dict[str, dict[str, Any]]:
    """Overrides an uploaded config.ini makes to the server defaults.

    The upload is read on top of the server's config.ini, so a partial file
    only changes what it names; the result goes through checked_overrides.
    """
    import configparser
    from pathlib import Path

    cp = configparser.ConfigParser()
    default_ini = Path(__file__).resolve().parents[2] / "config.ini"
    if default_ini.exists():
        cp.read(default_ini)
    try:
        cp.read_string(text)
        uploaded = RunConfig.from_configparser(cp).to_dict()
    except (configparser.Error, ValueError) as e:
        raise ConfigOverrideError(f"Invalid config file: {e}") from e
    current = base.to_dict()
    diff: dict[str, dict[str, Any]] = {}
    for section, values in uploaded.items():
        if not isinstance(values, dict):
            continue
        for field, value in values.items():
            if value != (current.get(section) or {}).get(field):
                diff.setdefault(section, {})[field] = value
    return checked_overrides(diff, base)


def resolve_run_config(preset: str | None, overrides: dict[str, dict[str, Any]] | None) -> RunConfig:
    """Server defaults, then the preset, then the (checked) user overrides."""
    config = RunConfig.from_default_ini()
    if preset:
        if preset not in PRESETS_BY_ID:
            raise ConfigOverrideError(
                f"Unknown preset: {preset} (one of {', '.join(PRESETS_BY_ID)})")
        config.apply_nested_overrides(PRESETS_BY_ID[preset]["overrides"])
    if overrides:
        config.apply_nested_overrides(overrides)
    return config
