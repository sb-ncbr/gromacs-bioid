import sys
import types

if "MDAnalysis" not in sys.modules:
    mdanalysis = types.ModuleType("MDAnalysis")
    mdanalysis.Universe = type("Universe", (), {})
    mdanalysis.AtomGroup = type("AtomGroup", (), {})
    sys.modules["MDAnalysis"] = mdanalysis

if "periodictable" not in sys.modules:
    periodictable = types.ModuleType("periodictable")
    periodictable.elements = []
    sys.modules["periodictable"] = periodictable

if "rdkit" not in sys.modules:
    rdkit = types.ModuleType("rdkit")
    chem = types.ModuleType("rdkit.Chem")
    determine_bonds = types.ModuleType("rdkit.Chem.rdDetermineBonds")
    chem.rdDetermineBonds = determine_bonds
    rdkit.Chem = chem
    sys.modules["rdkit"] = rdkit
    sys.modules["rdkit.Chem"] = chem
    sys.modules["rdkit.Chem.rdDetermineBonds"] = determine_bonds

from ... import src as project_src

sys.modules.setdefault("src", project_src)

from ...src.identifiers.identifier_resolvers import identifier_resolver as resolver_module
from ...src.identifiers.identifier_resolvers.identifier_resolver import (
    IdentifierResolutionError,
    IdentifierResolver,
)
from ...src.signatures.signature_generators.signature_generator import (
    SignatureGenerationError,
    SignatureGenerator,
    SignatureGeneratorType,
)


class FakeCache:
    def fetch_identity_identifiers(self, resolver_name, signature):
        return []

    def fetch_similarity_identifiers(self, resolver_name, signature):
        return []


class FailingIdentifierResolver(IdentifierResolver):
    def __init__(self, error):
        super().__init__("failing_identifier", "TEST_ID", ["smiles"])
        self.allowed_identity = True
        self.allowed_similarity = True
        self.error = error

    def _is_applicable(self, signature):
        return True

    def _resolve_identity(self, signature, working_directory):
        raise self.error

    def _resolve_similarity(self, signature, working_directory):
        raise self.error


class FailingSignatureGenerator(SignatureGenerator):
    def __init__(self, error):
        super().__init__("smiles", SignatureGeneratorType.ANALYTICAL, "smiles")
        self.generator_name = "failing_signature"
        self._is_allowed = True
        self.error = error

    def _is_applicable(self, simulation, fragment):
        return True

    def _generate_signature(self, simulation, fragment):
        raise self.error


def test_identifier_resolution_error_is_logged_and_returned_as_none(monkeypatch, caplog):
    monkeypatch.setattr(resolver_module, "ResolverCache", FakeCache)
    resolver = FailingIdentifierResolver(IdentifierResolutionError("database unavailable"))

    with caplog.at_level("INFO", logger="identifier"):
        assert resolver.resolve_signature("CCO", as_similarity=False, working_directory=".") is None

    assert "database unavailable" in caplog.text


def test_unexpected_identifier_error_is_logged_with_traceback(monkeypatch, caplog):
    monkeypatch.setattr(resolver_module, "ResolverCache", FakeCache)
    resolver = FailingIdentifierResolver(RuntimeError("malformed response"))

    with caplog.at_level("ERROR", logger="identifier"):
        assert resolver.resolve_signature("CCO", as_similarity=False, working_directory=".") is None

    assert "malformed response" in caplog.text


def test_signature_generation_error_is_logged_and_suppressed(caplog):
    generator = FailingSignatureGenerator(SignatureGenerationError("invalid representation"))

    with caplog.at_level("INFO", logger="signature"):
        assert generator.generate_signature(None, None) is None

    assert "invalid representation" in caplog.text


def test_unexpected_signature_error_is_logged_and_suppressed(caplog):
    generator = FailingSignatureGenerator(RuntimeError("unexpected generator failure"))

    with caplog.at_level("ERROR", logger="signature"):
        assert generator.generate_signature(None, None) is None

    assert "unexpected generator failure" in caplog.text
