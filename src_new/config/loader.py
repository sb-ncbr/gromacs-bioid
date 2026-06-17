from __future__ import annotations

import configparser
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Union, get_type_hints


@dataclass
class LoaderConfig:
    tpr_resid_from_one: bool = True
    guess_missing_elements: bool = True
    guess_missing_masses: bool = True
    guess_missing_names: bool = True
    guess_missing_bonds: bool = False
    quick_structure_search: bool = True
    element_mass_tolerance: float = 0.01
    bond_guess_vdw_factor: float = 0.55


@dataclass
class ExecutorConfig:
    n_threads: int = 10
    tps: int = 100
    emit_queue_stats: bool = True
    # Parallelism feature toggles (default False for backward compatibility)
    signatures_parallel: bool = False
    identifiers_parallel: bool = False
    verification_parallel: bool = False


@dataclass
class TaskTimeoutConfig:
    global_timeout_s: int = 600
    input_timeout_s: int = 5
    create_timeout_s: int = 5
    load_timeout_s: int = 300
    signatures_timeout_s: int = 2400
    identifiers_timeout_s: int = 1200
    summarize_timeout_s: int = 1200
    metadata_timeout_s: int = 1200


@dataclass
class SignaturesConfig:
    overwrite_existing: bool = False
    generation_attempts: int = 10
    smiles_maximum_number_of_atoms: int = 250
    fasta_map_determine_sequence_partial_mode: bool = False
    fasta_map_determine_sequence_strict_mode: bool = False
    name_minimum_length: int = 1
    # feature toggles
    smiles: bool = True
    smiles_not_sanitized: bool = True
    atom: bool = True
    fasta_map_protein: bool = True
    fasta_map_nucleic: bool = True
    fasta_resname_protein: bool = True
    fasta_resname_nucleic: bool = True
    pdb_protein: bool = True
    pdb_nucleic: bool = True
    pdb_not_sanitized_protein: bool = True
    pdb_not_sanitized_nucleic: bool = True
    pdb_backbone_protein: bool = True
    pdb_backbone_nucleic: bool = True
    pdb_backbone_not_sanitized_protein: bool = True
    pdb_backbone_not_sanitized_nucleic: bool = True
    topology_less_pdb: bool = True
    ca_only_pdb: bool = True
    name_chain: bool = True
    name_molecule: bool = True
    name_segment: bool = True
    fingerprint: bool = True
    # new signature generators
    inchi_key: bool = True
    morgan_fingerprint: bool = True
    selfies: bool = True
    molecular_formula: bool = True
    tdi: bool = True
    lipid_shorthand: bool = True
    glycan_composition: bool = True
    mmcif: bool = True


@dataclass
class IdentifiersConfig:
    overwrite_existing: bool = False
    blast_pdb_protein: bool = True
    blast_pdb_protein_similarity: bool = True
    blast_uniprot: bool = True
    blast_uniprot_similarity: bool = True
    blast_nr_protein: bool = True
    blast_nr_protein_similarity: bool = True
    blast_swissprot_protein: bool = True
    blast_swissprot_protein_similarity: bool = True
    blast_pdb_nucleic: bool = True
    blast_pdb_nucleic_similarity: bool = True
    blast_core_nt: bool = True
    blast_core_nt_similarity: bool = True
    blast_nt: bool = True
    blast_nt_similarity: bool = True
    pdb_struct_protein: bool = True
    pdb_struct_protein_similarity: bool = True
    pdb_struct_nucleotide: bool = True
    pdb_struct_nucleotide_similarity: bool = True
    alphafind_struct: bool = True
    alphafind_struct_similarity: bool = True
    chembl_struct: bool = True
    chembl_struct_similarity: bool = True
    pubchem_struct: bool = True
    pubchem_struct_similarity: bool = True
    atom: bool = True
    atom_similarity: bool = False
    idsm_pubchem: bool = True
    idsm_pubchem_similarity: bool = True
    idsm_chembl: bool = True
    idsm_chembl_similarity: bool = True
    idsm_chebi: bool = True
    idsm_chebi_similarity: bool = True
    name_ccd: bool = True
    name_ccd_similarity: bool = False
    name_maps: bool = True
    name_maps_similarity: bool = False
    name_manual: bool = True
    name_manual_similarity: bool = False


@dataclass
class BlastConfig:
    blastp_exec: str = "/usr/bin/blastp"
    blastn_exec: str = "/usr/bin/blastn"
    nr_aa_db: str = "/app/databases/nr/nr"           # non-redundant protein
    swissprot_aa_db: str = "/app/databases/swissprot/swissprot"  # curated protein
    pdb_aa_db: str = "/app/databases/pdbaa/pdbaa"       # PDB protein sequences
    pdb_nt_db: str = "/app/databases/pdbnt/pdbnt"       # PDB nucleotide sequences
    core_nt_db: str = "/app/databases/core_nt/core_nt"    # core nucleotide
    nt_db: str = "/app/databases/nt/nt"              # full nucleotide
    blastp_num_threads: int = 1
    blastn_num_threads: int = 1
    max_target_seqs: int = 500
    timeout_s: int = 300
    local_instance_run_short_search_if_under_X_residues: int = 30
    exact_match_max_evalue: float = 1e-50
    exact_match_min_bits: int = 51
    exact_match_min_identity_p: float = 0.99
    exact_match_min_query_cov_p: float = 0.99
    similarity_match_max_evalue: float = 0.1
    similarity_match_min_bits: int = 20
    similarity_match_min_identity_p: float = 0.4
    similarity_match_min_query_cov_p: float = 0.15


@dataclass
class ChemblConfig:
    similarity_threshold: int = 60


@dataclass
class IdsmConfig:
    similarity_threshold: int = 80


@dataclass
class PubchemConfig:
    similarity_threshold: int = 95
    retry_attempts: int = 1
    retry_delay_s: int = 10


@dataclass
class AlphafindConfig:
    url: str = "https://api.stage.alphafind.dyn.cloud.e-infra.cz/search?limit=50&offset=0&superposition=true"
    retry_count: int = 2
    retry_delay_s: int = 5
    request_timeout_s: int = 30
    poll_interval_s: int = 5
    max_poll_attempts: int = 20




@dataclass
class PDBConfig:
    use_deployment_file_access: bool = True
    deployment_file_url: str = "https://bioid.dyn.cloud.e-infra.cz"
    curr_uuid: str = ""  # runtime field, set by API/Celery

@dataclass
class FoldseekConfig:
    foldseek_exec: str = "foldseek"
    db_path: str = ""  # empty = use default AFDB


@dataclass
class IdentifiersCacheConfig:
    directory: str = "/app/runs"
    file: str = "resolver_cache.sqlite3"


@dataclass
class NamesConfig:
    ccd_db: str = "databases/ccd.json"
    maps_db: str = "databases/maps.json"
    manual_db: str = "databases/manual.json"



@dataclass
class VerificationConfig:
    verify_top_n: int = 100
    similarity_top_n: int = 10
    enable_annotation_quality: bool = True
    resolver_weight: float = 0.4
    similarity_weight: float = 0.4
    annotation_weight: float = 0.2
    tm_score_threshold: float = 0.5
    min_final_confidence: float = 0.0



ConfigSection = Union[
    LoaderConfig,
    ExecutorConfig,
    TaskTimeoutConfig,
    SignaturesConfig,
    IdentifiersConfig,
    IdentifiersCacheConfig,
    BlastConfig,
    ChemblConfig,
    IdsmConfig,
    PubchemConfig,
    AlphafindConfig,
    PDBConfig,
    FoldseekConfig,
    NamesConfig,
    VerificationConfig,
]


@dataclass
class RunConfig:
    """Run-level configuration combining all sections."""
    loader: LoaderConfig = field(default_factory=LoaderConfig)
    executor: ExecutorConfig = field(default_factory=ExecutorConfig)
    timeouts: TaskTimeoutConfig = field(default_factory=TaskTimeoutConfig)
    signatures: SignaturesConfig = field(default_factory=SignaturesConfig)
    identifiers: IdentifiersConfig = field(default_factory=IdentifiersConfig)
    identifiers_cache: IdentifiersCacheConfig = field(default_factory=IdentifiersCacheConfig)
    blast: BlastConfig = field(default_factory=BlastConfig)
    chembl: ChemblConfig = field(default_factory=ChemblConfig)
    idsm: IdsmConfig = field(default_factory=IdsmConfig)
    pubchem: PubchemConfig = field(default_factory=PubchemConfig)
    alphafind: AlphafindConfig = field(default_factory=AlphafindConfig)
    pdb: PDBConfig = field(default_factory=PDBConfig)
    foldseek: FoldseekConfig = field(default_factory=FoldseekConfig)
    names: NamesConfig = field(default_factory=NamesConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)

    # raw overrides map (for runtime edits from web UI)
    _overrides: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_configparser(cls, cp: configparser.ConfigParser) -> RunConfig:
        """Build from a ConfigParser instance."""
        config = cls()

        # Mapping of section names to config attributes and their dataclasses
        section_mapping = {
            "loader": ("loader", LoaderConfig),
            "tasks": ("executor", ExecutorConfig),
            "timeouts": ("timeouts", TaskTimeoutConfig),
            "signatures": ("signatures", SignaturesConfig),
            "identifiers": ("identifiers", IdentifiersConfig),
            "identifiers_cache": ("identifiers_cache", IdentifiersCacheConfig),
            "blast": ("blast", BlastConfig),
            "chembl": ("chembl", ChemblConfig),
            "idsm": ("idsm", IdsmConfig),
            "pubchem": ("pubchem", PubchemConfig),
            "ALPHAFIND": ("alphafind", AlphafindConfig),
            "alphafind": ("alphafind", AlphafindConfig),
            "PDB": ("pdb", PDBConfig),
            "foldseek": ("foldseek", FoldseekConfig),
            "names": ("names", NamesConfig),
        
            "verification": ("verification", VerificationConfig),
        }

        for section_name, (attr_name, dataclass_type) in section_mapping.items():
            if cp.has_section(section_name):
                section_config = getattr(config, attr_name)
                # Get type hints for proper type resolution
                type_hints = get_type_hints(dataclass_type)
                for field_name in dataclass_type.__dataclass_fields__:
                    if cp.has_option(section_name, field_name):
                        field_type = type_hints.get(field_name, str)
                        value = cls._get_config_value(cp, section_name, field_name, field_type)
                        setattr(section_config, field_name, value)

        # Handle miscellaneous section for uid_length, temporary_directory, use_temporary_directory
        if cp.has_section("miscellaneous"):
            if cp.has_option("miscellaneous", "uid_length"):
                config._overrides["miscellaneous.uid_length"] = cp.getint("miscellaneous", "uid_length")
            if cp.has_option("miscellaneous", "temporary_directory"):
                config._overrides["miscellaneous.temporary_directory"] = cp.get("miscellaneous", "temporary_directory")
            if cp.has_option("miscellaneous", "use_temporary_directory"):
                config._overrides["miscellaneous.use_temporary_directory"] = cp.getboolean("miscellaneous", "use_temporary_directory")

        return config

    @staticmethod
    def _get_config_value(cp: configparser.ConfigParser, section: str, option: str, field_type: type) -> Any:
        """Get a config value with proper type conversion."""
        # Handle basic types
        if field_type is bool:
            return cp.getboolean(section, option)
        elif field_type is int:
            return cp.getint(section, option)
        elif field_type is float:
            return cp.getfloat(section, option)
        elif field_type is str:
            return cp.get(section, option)
        else:
            # Default to string for unknown types
            return cp.get(section, option)

    @classmethod
    def from_ini_path(cls, path: Union[str, Path]) -> RunConfig:
        """Load from an INI file path."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        
        cp = configparser.ConfigParser()
        cp.read(path)
        return cls.from_configparser(cp)

    @classmethod
    def from_default_ini(cls) -> RunConfig:
        """Load from the repo root config.ini. Falls back to RunConfig() if not found."""
        # Find config.ini relative to this file's location (repo root)
        repo_root = Path(__file__).resolve().parents[2]
        config_path = repo_root / "config.ini"
        
        if not config_path.exists():
            return cls()
        
        cp = configparser.ConfigParser()
        cp.read(config_path)
        return cls.from_configparser(cp)

    def override(self, path: str, value: Any) -> None:
        """Override a single value by dot-path, e.g. 'loader.guess_missing_elements' = False."""
        parts = path.split(".")
        if len(parts) != 2:
            raise ValueError(f"Invalid override path: {path}. Expected format: 'section.field'")
        
        section_name, field_name = parts
        
        # Get the section object
        if not hasattr(self, section_name):
            raise ValueError(f"Unknown config section: {section_name}")
        
        section_obj = getattr(self, section_name)
        
        # Check if field exists in the section
        if not hasattr(section_obj, field_name):
            raise ValueError(f"Unknown config field: {field_name} in section {section_name}")
        
        # Store the override
        self._overrides[path] = value
        
        # Apply the override
        setattr(section_obj, field_name, value)

    def save_overrides(self, path: Union[str, Path]) -> None:
        """Save runtime overrides to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._overrides, f, indent=2)

    @classmethod
    def load_overrides(cls, path: Union[str, Path]) -> dict[str, Any]:
        """Load runtime overrides from a JSON file."""
        path = Path(path)
        if not path.exists():
            return {}
        with open(path, "r") as f:
            return json.load(f)

    def apply_overrides(self, overrides: dict[str, Any]) -> None:
        """Apply a dictionary of overrides with flat dot-path keys."""
        for path, value in overrides.items():
            self.override(path, value)

    def apply_nested_overrides(self, nested: dict[str, Any]) -> None:
        """Apply a nested dictionary of overrides, walking dicts and building dot-paths.
        
        Traverses nested dicts and calls self.override(path, value) for each leaf,
        building dot-paths like "signatures.smiles". Skips keys starting with "_".
        """
        def walk(obj: Any, prefix: str = "") -> None:
            if not isinstance(obj, dict):
                return
            for key, value in obj.items():
                if key.startswith("_"):
                    continue
                path = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    walk(value, path)
                else:
                    self.override(path, value)
        
        walk(nested)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunConfig:
        """Reconstruct RunConfig from a dictionary (e.g., from JSON).
        
        Args:
            d: Dictionary with config structure from to_dict().
            
        Returns:
            New RunConfig instance with values from the dictionary.
        """
        config = cls()
        for section_name, section_data in d.items():
            if section_name.startswith("_"):
                continue
            if not hasattr(config, section_name):
                continue
            section_obj = getattr(config, section_name)
            if hasattr(section_obj, "__dataclass_fields__"):
                for field_name, field_value in section_data.items():
                    if hasattr(section_obj, field_name):
                        setattr(section_obj, field_name, field_value)
        return config

    def to_dict(self) -> dict[str, Any]:
        """Convert config to a JSON-serializable dictionary."""
        result = {}
        for field_name in self.__dataclass_fields__:
            if field_name.startswith("_"):
                continue
            field_value = getattr(self, field_name)
            if hasattr(field_value, "__dataclass_fields__"):
                result[field_name] = asdict(field_value)
            else:
                result[field_name] = field_value
        return result

    def to_ini_path(self, path: Union[str, Path]) -> None:
        """Write the current config state to an INI file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        cp = configparser.ConfigParser()
        
        section_mapping = {
            "loader": "loader",
            "executor": "tasks",
            "timeouts": "timeouts",
            "signatures": "signatures",
            "identifiers": "identifiers",
            "identifiers_cache": "identifiers_cache",
            "blast": "blast",
            "chembl": "chembl",
            "idsm": "idsm",
            "pubchem": "pubchem",
            "alphafind": "ALPHAFIND",
            "pdb": "PDB",
            "foldseek": "foldseek",
            "names": "names",
            "verification": "verification",
        }
        
        for attr_name, section_name in section_mapping.items():
            if not hasattr(self, attr_name):
                continue
            
            section_obj = getattr(self, attr_name)
            if not hasattr(section_obj, "__dataclass_fields__"):
                continue
            
            cp.add_section(section_name)
            
            for field_name in section_obj.__dataclass_fields__:
                value = getattr(section_obj, field_name)
                if isinstance(value, bool):
                    value = "yes" if value else "no"
                cp.set(section_name, field_name, str(value))
        
        with open(path, "w") as f:
            cp.write(f)


def load_config_from_path(path: Union[str, Path]) -> RunConfig:
    """Load configuration from an INI file path."""
    return RunConfig.from_ini_path(path)


def merge_with_dict(config: RunConfig, overrides: dict[str, Any]) -> RunConfig:
    """Merge a dictionary of overrides into the config."""
    config.apply_overrides(overrides)
    return config
