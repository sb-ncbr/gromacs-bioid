"""Tests for the configuration system."""

import configparser
import json
import tempfile
from pathlib import Path

import pytest

from src_new.config.loader import (
    RunConfig,
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
    load_config_from_path,
    merge_with_dict,
)


class TestLoadFromConfigParser:
    """Test loading configuration from ConfigParser."""

    def test_load_from_configparser(self):
        """Test loading loader config section."""
        cp = configparser.ConfigParser()
        cp.add_section("loader")
        cp.set("loader", "guess_missing_elements", "yes")
        cp.set("loader", "guess_missing_bonds", "no")
        cp.set("loader", "element_mass_tolerance", "0.05")

        config = RunConfig.from_configparser(cp)

        assert config.loader.guess_missing_elements is True
        assert config.loader.guess_missing_bonds is False
        assert config.loader.element_mass_tolerance == 0.05

    def test_load_executor_config(self):
        """Test loading executor/tasks config section."""
        cp = configparser.ConfigParser()
        cp.add_section("tasks")
        cp.set("tasks", "n_threads", "20")
        cp.set("tasks", "tps", "50")
        cp.set("tasks", "emit_queue_stats", "no")

        config = RunConfig.from_configparser(cp)

        assert config.executor.n_threads == 20
        assert config.executor.tps == 50
        assert config.executor.emit_queue_stats is False

    def test_load_signatures_config(self):
        """Test loading signatures config section."""
        cp = configparser.ConfigParser()
        cp.add_section("signatures")
        cp.set("signatures", "smiles", "no")
        cp.set("signatures", "overwrite_existing", "yes")
        cp.set("signatures", "generation_attempts", "5")

        config = RunConfig.from_configparser(cp)

        assert config.signatures.smiles is False
        assert config.signatures.overwrite_existing is True
        assert config.signatures.generation_attempts == 5

    def test_load_blast_config(self):
        """Test loading blast config section."""
        cp = configparser.ConfigParser()
        cp.add_section("blast")
        cp.set("blast", "blastp_exec", "/custom/path/blastp")
        cp.set("blast", "exact_match_max_evalue", "1e-30")
        cp.set("blast", "local_instance_run_short_search_if_under_X_residues", "50")

        config = RunConfig.from_configparser(cp)

        assert config.blast.blastp_exec == "/custom/path/blastp"
        assert config.blast.exact_match_max_evalue == 1e-30
        assert config.blast.local_instance_run_short_search_if_under_X_residues == 50

    def test_load_identifiers_config(self):
        """Test loading identifiers config section."""
        cp = configparser.ConfigParser()
        cp.add_section("identifiers")
        cp.set("identifiers", "blast_pdb_protein", "no")
        cp.set("identifiers", "atom_similarity", "yes")

        config = RunConfig.from_configparser(cp)

        assert config.identifiers.blast_pdb_protein is False
        assert config.identifiers.atom_similarity is True


class TestLoadFromIniFile:
    """Test loading configuration from INI file."""

    def test_load_from_ini_file(self):
        """Test loading from a temp INI file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write("[signatures]\n")
            f.write("smiles = no\n")
            f.write("fingerprint = no\n")
            f.write("name_minimum_length = 5\n")
            temp_path = f.name

        try:
            config = RunConfig.from_ini_path(temp_path)

            assert config.signatures.smiles is False
            assert config.signatures.fingerprint is False
            assert config.signatures.name_minimum_length == 5
        finally:
            Path(temp_path).unlink()

    def test_load_from_nonexistent_file_raises(self):
        """Test that loading from nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            RunConfig.from_ini_path("/nonexistent/path/config.ini")

    def test_load_multiple_sections(self):
        """Test loading multiple sections from INI file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write("[loader]\n")
            f.write("guess_missing_elements = no\n")
            f.write("[blast]\n")
            f.write("blastp_exec = /opt/blast/bin/blastp\n")
            f.write("[identifiers]\n")
            f.write("chembl_struct = no\n")
            temp_path = f.name

        try:
            config = RunConfig.from_ini_path(temp_path)

            assert config.loader.guess_missing_elements is False
            assert config.blast.blastp_exec == "/opt/blast/bin/blastp"
            assert config.identifiers.chembl_struct is False
        finally:
            Path(temp_path).unlink()


class TestOverride:
    """Test runtime overrides."""

    def test_override_changes_value(self):
        """Test that override changes a config value."""
        config = RunConfig()
        
        # Override a timeout value
        config.override("timeouts.load_timeout_s", 999)

        assert config.timeouts.load_timeout_s == 999
        assert "timeouts.load_timeout_s" in config._overrides
        assert config._overrides["timeouts.load_timeout_s"] == 999

    def test_override_loader_config(self):
        """Test overriding loader config values."""
        config = RunConfig()

        config.override("loader.guess_missing_elements", False)
        config.override("loader.bond_guess_vdw_factor", 0.75)

        assert config.loader.guess_missing_elements is False
        assert config.loader.bond_guess_vdw_factor == 0.75
        assert len(config._overrides) == 2

    def test_override_invalid_path_raises(self):
        """Test that invalid override path raises ValueError."""
        config = RunConfig()

        with pytest.raises(ValueError, match="Invalid override path"):
            config.override("invalid_path", "value")

    def test_override_unknown_section_raises(self):
        """Test that unknown section raises ValueError."""
        config = RunConfig()

        with pytest.raises(ValueError, match="Unknown config section"):
            config.override("unknown_section.field", "value")

    def test_override_unknown_field_raises(self):
        """Test that unknown field raises ValueError."""
        config = RunConfig()

        with pytest.raises(ValueError, match="Unknown config field"):
            config.override("loader.unknown_field", "value")


class TestSaveAndLoadOverrides:
    """Test saving and loading overrides."""

    def test_save_overrides(self):
        """Test saving overrides to JSON file."""
        config = RunConfig()
        config.override("loader.guess_missing_elements", False)
        config.override("executor.n_threads", 4)

        with tempfile.TemporaryDirectory() as tmpdir:
            override_path = Path(tmpdir) / "overrides.json"
            config.save_overrides(override_path)

            assert override_path.exists()
            with open(override_path) as f:
                saved = json.load(f)

            assert saved["loader.guess_missing_elements"] is False
            assert saved["executor.n_threads"] == 4

    def test_load_overrides(self):
        """Test loading overrides from JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            override_path = Path(tmpdir) / "overrides.json"
            overrides = {
                "signatures.smiles": False,
                "blast.exact_match_max_evalue": 1e-40
            }
            with open(override_path, "w") as f:
                json.dump(overrides, f)

            loaded = RunConfig.load_overrides(override_path)

            assert loaded["signatures.smiles"] is False
            assert loaded["blast.exact_match_max_evalue"] == 1e-40

    def test_load_overrides_nonexistent_file(self):
        """Test loading overrides from nonexistent file returns empty dict."""
        result = RunConfig.load_overrides("/nonexistent/path/overrides.json")
        assert result == {}

    def test_apply_overrides(self):
        """Test applying a dictionary of overrides."""
        config = RunConfig()
        overrides = {
            "loader.guess_missing_bonds": True,
            "timeouts.global_timeout_s": 1200
        }

        config.apply_overrides(overrides)

        assert config.loader.guess_missing_bonds is True
        assert config.timeouts.global_timeout_s == 1200
        assert len(config._overrides) == 2


class TestToDict:
    """Test converting config to dictionary."""

    def test_to_dict_produces_serializable_output(self):
        """Test that to_dict produces JSON-serializable output."""
        config = RunConfig()
        config.override("loader.guess_missing_elements", False)

        result = config.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert json_str is not None

        # Should contain all sections
        assert "loader" in result
        assert "executor" in result
        assert "timeouts" in result
        assert "signatures" in result
        assert "identifiers" in result
        assert "blast" in result
        assert "chembl" in result
        assert "idsm" in result
        assert "pubchem" in result
        assert "alphafind" in result

        # Should NOT contain _overrides
        assert "_overrides" not in result

    def test_to_dict_reflects_overrides(self):
        """Test that to_dict reflects overridden values."""
        config = RunConfig()
        config.override("executor.n_threads", 99)

        result = config.to_dict()

        assert result["executor"]["n_threads"] == 99


class TestMergeWithDict:
    """Test merge_with_dict function."""

    def test_merge_with_dict(self):
        """Test merging config with dict."""
        config = RunConfig()
        overrides = {
            "signatures.atom": False,
            "identifiers.blast_uniprot": False
        }

        result = merge_with_dict(config, overrides)

        assert result is config  # Should return same object
        assert config.signatures.atom is False
        assert config.identifiers.blast_uniprot is False


class TestLoadConfigFromPath:
    """Test load_config_from_path function."""

    def test_load_config_from_path(self):
        """Test loading config from path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write("[loader]\n")
            f.write("guess_missing_names = no\n")
            temp_path = f.name

        try:
            config = load_config_from_path(temp_path)

            assert config.loader.guess_missing_names is False
        finally:
            Path(temp_path).unlink()


class TestDefaultValues:
    """Test default configuration values."""

    def test_default_loader_config(self):
        """Test default loader config values."""
        config = RunConfig()

        assert config.loader.tpr_resid_from_one is True
        assert config.loader.guess_missing_elements is True
        assert config.loader.guess_missing_bonds is False
        assert config.loader.element_mass_tolerance == 0.01
        assert config.loader.bond_guess_vdw_factor == 0.55

    def test_default_executor_config(self):
        """Test default executor config values."""
        config = RunConfig()

        assert config.executor.n_threads == 10
        assert config.executor.tps == 100
        assert config.executor.emit_queue_stats is True

    def test_default_timeouts_config(self):
        """Test default timeouts config values."""
        config = RunConfig()

        assert config.timeouts.global_timeout_s == 600
        assert config.timeouts.load_timeout_s == 300
        assert config.timeouts.signatures_timeout_s == 2400

    def test_default_signatures_config(self):
        """Test default signatures config values."""
        config = RunConfig()

        assert config.signatures.smiles is True
        assert config.signatures.fingerprint is True
        assert config.signatures.overwrite_existing is False

    def test_default_blast_config(self):
        """Test default blast config values."""
        config = RunConfig()

        assert config.blast.blastp_exec == "/usr/bin/blastp"
        assert config.blast.blastn_exec == "/usr/bin/blastn"
        assert config.blast.exact_match_max_evalue == 1e-50

    def test_default_chembl_config(self):
        """Test default chembl config values."""
        config = RunConfig()

        assert config.chembl.similarity_threshold == 60

    def test_default_idsm_config(self):
        """Test default idsm config values."""
        config = RunConfig()

        assert config.idsm.similarity_threshold == 80

    def test_default_pubchem_config(self):
        """Test default pubchem config values."""
        config = RunConfig()

        assert config.pubchem.similarity_threshold == 95
        assert config.pubchem.retry_attempts == 1
        assert config.pubchem.retry_delay_s == 10

    def test_default_alphafind_config(self):
        """Test default alphafind config values."""
        config = RunConfig()

        assert config.alphafind.retry_count == 2
        assert config.alphafind.retry_delay_s == 5
        assert config.alphafind.request_timeout_s == 30

        assert config.alphafind.poll_interval_s == 5
        assert config.alphafind.max_poll_attempts == 20
        assert "limit=50" in config.alphafind.url
        assert "offset=0" in config.alphafind.url
        assert "superposition=true" in config.alphafind.url
