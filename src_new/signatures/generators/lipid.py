"""Lipid shorthand signature generator."""

from __future__ import annotations

import logging

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance, MoleculeType
from ...loader.universe_facade import LoadedUniverse
from ...molecules.lipid_names import LIPID21_HEADS, LIPID21_TAIL_CHAINS
from ..forcefield_maps import LIPID_FORCEFIELD_MAPS
from ..base import SignatureGenerator

logger = logging.getLogger("base")




# B-15 (red-team 4.9): AMBER Lipid14/17/21 split a lipid into one head
# residue (PC/PE/PG/PS) and two tail residues named by the fatty acid.
# (2026-11-21: moved to molecules/lipid_names, the typing uses them too)
_LIPID21_HEADS = LIPID21_HEADS
_LIPID21_TAILS = LIPID21_TAIL_CHAINS


def _lipid21_composition(resnames) -> str | None:
    """Compose a shorthand from an AMBER Lipid14/17/21 head+tail residue
    split (e.g. {PC, PA, OL} -> 'PC(16:0/18:1(9Z))'). None when the
    multiset is not exactly one head + two tails."""
    names = [str(r).upper() for r in resnames]
    heads = [n for n in names if n in _LIPID21_HEADS]
    tails = [n for n in names if n in _LIPID21_TAILS]
    if len(heads) != 1 or len(tails) != 2 or len(heads) + len(tails) != len(names):
        return None
    t1, t2 = sorted((_LIPID21_TAILS[t] for t in tails),
                    key=lambda t: (int(t.split(":")[0]), t))
    return f"{heads[0]}({t1}/{t2})"


class LipidShorthandGenerator(SignatureGenerator):
    """Lipid shorthand generator using force-field maps."""
    
    name = "lipid_shorthand"
    signature_type = "lipid_shorthand"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        # 2026-11-21 (mdval audit item 8b): a coarse-grained lipid has no
        # atoms to verify a LIPID MAPS structure against (every candidate
        # was rejected, fingerprint_unavailable) — its Martini name is
        # carried as a by-name lead instead (fragment_store).
        if (getattr(instance, "provenance", None) or {}).get("coarse_grained"):
            return False
        return instance.molecule_type == MoleculeType.LIPID
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        # all-atom names (2026-11-21, mdval audit item 4: ~200 CHARMM36 /
        # CHARMM-GUI / Slipids names from molecules/lipid_names)
        ff_maps = LIPID_FORCEFIELD_MAPS.get("charmm36", {})
        
        # B-15: keep the multiset — Lipid21 splits repeat tail residues
        # (PC + PA + PA), a set() would collapse them
        resnames = list(fragment.residues.resnames)
        
        if len(resnames) == 1:
            # Single residue type - look up in map
            resname = resnames[0].upper()
            if resname in ff_maps:
                return ff_maps[resname]
        elif len(resnames) > 1:
            # Multiple residues - check if all map to same shorthand
            shorthands = set()
            for resname in set(resnames):
                shorthand = ff_maps.get(resname.upper())
                if shorthand:
                    shorthands.add(shorthand)
            
            if len(shorthands) == 1:
                return shorthands.pop()

            # B-15: AMBER Lipid21 head+tail split compositions
            composed = _lipid21_composition(resnames)
            if composed:
                return composed

        # B-15: unmapped lipids used to emit the literal "LIPID", which the
        # resolver shipped verbatim to lipidmaps.org (always a miss) —
        # degrade with a reason (None) instead
        logger.debug("lipid_shorthand: no mapping for resnames %s", resnames)
        return None
