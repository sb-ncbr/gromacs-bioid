"""Pipeline step definitions for the BAT3 pipeline."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from ..executor.task import Task, StepResult
from ..signatures.generators._perceive_cache import (
    _h_deficiency, _external_cut_counts)


def _segment_flags(fragment) -> list:
    """Per-segment signature provenance flags (B-10 h_inferred,
    B-08 xbond_capped)."""
    flags = []
    if _h_deficiency(fragment) is not None:
        flags.append("h_inferred")
    try:
        if _external_cut_counts(fragment):
            flags.append("xbond_capped")
    except Exception:
        pass
    return flags
from ..input.discovery import inspect_directory, select_best_file_combination
from ..loader.strategies import load_simulation, summarize_load_failure
from ..loader.repair import TopologyRepair
from ..loader.unwrap import PbcRepair, PbcRepairReport
from ..loader.universe_facade import LoadedUniverse
from ..loader.fragment_store import FragmentStore
from ..loader.export_mmcif import export_system_mmcif, export_segment_mmcif
from ..verification.manager import VerificationManager

logger = logging.getLogger("base")


# ---------------------------------------------------------------------------
# Cooperative per-stage time budget (2026-09-19 stall fix)
#
# The pipeline contract is ~10 minutes per entry even for heavy systems
# (inputs are pre-downloaded). Postmortem evidence: individual compute
# stages (generate_signatures / identify_molecules / verify_results) parked
# for 1-4+ HOURS per entry due to resolver/fetch fan-out, dominating the
# 12h sweeper window and freezing throughput to zero for days.
#
# Mechanism: the executor injects a wall-clock deadline into the context
# before calling each handler (`stage_deadline_epoch`); stage handlers check
# it inside their natural loops via `_budget_exceeded()` and break early,
# recording a 'stage_time_budget' warning and continuing. Per-stage budgets
# (seconds) come from VALIDATION_STAGE_BUDGETS (JSON map), default below;
# VALIDATION_STAGE_BUDGETS=off disables budgeting.
# ---------------------------------------------------------------------------

_STAGE_BUDGET_STATE_KEY = "stage_deadline_epoch"
_STAGE_BUDGET_DEFAULT_S = int(os.environ.get("VALIDATION_STAGE_BUDGET_DEFAULT_S", "900"))

# ---------------------------------------------------------------------------
# Stage error persistence (N1 / F-N1e): generator and resolver failures were
# previously only converted to log warnings, making whole dead-channel classes
# invisible postmortem (N1 audit 2026-10-03). Errors are persisted to
# results.json under a SEPARATE top-level branch `stage_errors/signatures/{seg}`
# and `stage_errors/identifiers/{frag}` — deliberately NOT nested inside
# signatures/{seg}/ or identifiers/{frag}/ because the verification stage
# iterates those dictionaries (an extra key would be read as a bogus
# generator/resolver entry). Bounded to keep results.json size in check.
# ---------------------------------------------------------------------------
_STAGE_ERRORS_MAX_PER_SEGMENT = 20
_STAGE_ERROR_MAX_CHARS = 300


def bounded_stage_errors(errors: list) -> list[dict]:
    """Normalize+bound stage error records for results.json persistence.

    - keep at most _STAGE_ERRORS_MAX_PER_SEGMENT entries
    - truncate error text to _STAGE_ERROR_MAX_CHARS
    - keep only {generator,resolver}(if present)+error; input NOT mutated
    - non-dict entries and empty messages are dropped
    """
    out: list[dict] = []
    if not isinstance(errors, list):
        return out
    for entry in errors[: _STAGE_ERRORS_MAX_PER_SEGMENT]:
        if not isinstance(entry, dict):
            continue
        msg = str(entry.get("error", "") or "")[: _STAGE_ERROR_MAX_CHARS]
        if not msg:
            continue
        rec: dict = {}
        if entry.get("generator"):
            rec["generator"] = str(entry["generator"])
        if entry.get("resolver"):
            rec["resolver"] = str(entry["resolver"])
        rec["error"] = msg
        out.append(rec)
    return out

_STAGE_BUDGETS_DEFAULT = {
    "generate_signatures": 1200,
    "identify_molecules": 1200,
    "verify_results": 1200,
}


def _stage_budget_seconds(step_id: str) -> int | None:
    """Return the budget in seconds for a stage, or None if disabled."""
    raw = os.environ.get("VALIDATION_STAGE_BUDGETS", "")
    if raw.strip().lower() == "off":
        return None
    try:
        mapping = json.loads(raw) if raw else {}
    except Exception:
        mapping = {}
    mapping = {**_STAGE_BUDGETS_DEFAULT, **mapping}
    return int(mapping.get(step_id, _STAGE_BUDGET_DEFAULT_S))


def set_stage_budget(context, step_id: str) -> None:
    """Store this stage's wall-clock deadline in the context (idempotent)."""
    budget = _stage_budget_seconds(step_id)
    if budget is None:
        return
    try:
        context.set_value(_STAGE_BUDGET_STATE_KEY, time.time() + budget)
    except Exception:
        pass


def budget_deadline(context) -> float | None:
    """Read the active stage deadline from context (None if unset)."""
    try:
        return context.get_value(_STAGE_BUDGET_STATE_KEY)
    except Exception:
        return None


def _budget_exceeded(context) -> bool:
    """True when the current stage has overrun its wall-clock budget."""
    dl = budget_deadline(context)
    return dl is not None and time.time() > dl


# W3.1-3 (A6): grace granted to the MERGE phase after a generation cut
_MERGE_GRACE_S = 60


def structure_search_unavailable_reason(config) -> str | None:
    """W3.1 item 4 (A9): why RCSB structure similarity search will be
    skipped for EVERY segment in this run, or None when it works.

    Silent-skip defect: Celery-dispatched runs have no registry uuid
    (config.pdb.curr_uuid empty), so both structure-search resolvers
    skipped every query with only a log line ("curr_uuid is empty") —
    the results payload never said structure search was off. Adhoc
    staging (BAT3_ADHOC_DIR) is the fix for those runs; when it is
    unset or unwritable the run now says so, loudly, once."""
    pdb = getattr(config, "pdb", None)
    if pdb is None or not getattr(pdb, "use_deployment_file_access", False):
        return None  # upload mode: no API URL dependency
    if getattr(pdb, "curr_uuid", ""):
        return None  # registry runs use /files/{uuid}/input/ — works
    adhoc = (getattr(pdb, "adhoc_files_dir", "") or "").strip()
    if not adhoc:
        return ("structure search unavailable: BAT3_ADHOC_DIR is not set "
                "and this run has no registry uuid (Celery-dispatched); "
                "every RCSB similarity query would be skipped")
    try:
        root = Path(adhoc)
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".w31_adhoc_probe"
        probe.write_text("")
        probe.unlink()
    except Exception as exc:
        return (f"structure search unavailable: adhoc dir {adhoc!r} is "
                f"not writable ({exc}); RCSB similarity queries would "
                f"fail to stage")
    return None


def _maybe_warn_structure_search(context, config) -> None:
    """Emit the structure_search_unavailable warning once per run."""
    reason = structure_search_unavailable_reason(config)
    if not reason:
        return
    try:
        results = context.results
        if results.get_data("identification/structure_search_unavailable"):
            return  # already warned for this run
        results.set_data("identification/structure_search_unavailable",
                         {"reason": reason})
    except Exception:
        pass
    context.add_warning("structure_search_unavailable", reason)


def _grant_merge_grace(context) -> None:
    """W3.1-3 (A6): a budget cut during generation must still MERGE what
    was already computed. Re-checking the exhausted generation deadline
    in the merge loop discarded every partial (M05 with a 2 s budget: 2 s
    of chemistry computed, 0 signatures persisted). Grant the merge a
    fresh, bounded grace so partials survive — slow merges still cut."""
    try:
        context.set_value(_STAGE_BUDGET_STATE_KEY, time.time() + _MERGE_GRACE_S)
    except Exception:
        pass


def _discover_input(context):
    """Discover input files and determine loading strategy."""
    bundle = inspect_directory(context.working_directory)
    decision = select_best_file_combination(bundle)

    context.record_data("input/bundle", bundle.to_dict())
    context.record_data("input/decision", decision.to_dict())

    input_kind_str = decision.input_kind.value if decision.input_kind else None
    if input_kind_str:
        context.record_data("input/kind", input_kind_str)
        # Update pipeline metadata in results
        if hasattr(context.results, 'set_pipeline_field'):
            context.results.set_pipeline_field("input_kind", input_kind_str)

    return StepResult(
        summary={"discovered": True, "input_kind": input_kind_str},
        context_updates={"input_bundle": bundle, "load_decision": decision}
    )


def _load_simulation(context):
    """Load the simulation using the discovered strategy."""
    decision = context.get_value("load_decision")
    bundle = context.get_value("input_bundle")

    if not decision or not bundle:
        context.fail("missing_input", "Input discovery did not produce a load decision")

    result = load_simulation(decision, bundle, context.config, context.results)
    if not result.success:
        # bughunt BH-014: carry the structured failure reason (atom-count
        # mismatch with both counts, content gates, first real exception)
        # into the critical error details instead of the generic message.
        summary = summarize_load_failure(result.attempts)
        context.fail(
            "load_failed",
            f"No loading strategy succeeded after {len(result.attempts)} "
            f"attempts: {summary['message']}",
            details={
                "reason": summary["reason"],
                "attempts": [
                    {
                        "strategy": getattr(a, "strategy", None),
                        "strategy_name": getattr(getattr(a, "strategy", None), "value", None),
                        "status": getattr(a, "status", None),
                        "error_code": getattr(a, "error_code", None),
                        "error_message": getattr(a, "error_message", None),
                    }
                    for a in result.attempts
                ],
            },
        )

    # Surface coordinate-scale corrections as coded run warnings (UI catalog).
    if result.scale_report and result.scale_report.get("warning_code"):
        context.add_warning(
            result.scale_report["warning_code"],
            result.scale_report["warning_message"],
            details=result.scale_report,
        )

    context.record_data("simulation/n_atoms", result.universe.atoms.n_atoms)
    return StepResult(
        summary={"loaded": True, "strategy": result.final_strategy.value if result.final_strategy else None},
        context_updates={"universe": result.universe}
    )


def _repair_topology(context):
    """Repair missing topology attributes (elements, masses, names, bonds)."""
    universe = context.get_value("universe")
    if not universe:
        context.fail("missing_universe", "No universe loaded for repair")

    repair = TopologyRepair(universe, context.config)
    report = repair.run()

    # Check for insufficient bonds and warn if guessing was disabled
    bond_count = len(universe.atoms.bonds) if hasattr(universe.atoms, 'bonds') else 0
    atom_count = universe.atoms.n_atoms
    if not repair._has_sufficient_bonds() and not context.config.loader.guess_missing_bonds:
        context.add_warning(
            "insufficient_bonds",
            f"Bond topology appears insufficient ({bond_count} bonds for {atom_count} atoms). "
            "Molecule detection and signature generation will likely fail. "
            "Consider enabling 'guess_missing_bonds' in the loader configuration.",
            details={"bond_count": bond_count, "atom_count": atom_count}
        )

    context.record_data("repair/report", report.to_dict())
    return StepResult(
        summary={"repaired": True, **report.to_dict()},
        context_updates={"repair_report": report}
    )


def _unwrap_periodic_boundaries(context):
    """Unwrap periodic boundary conditions for single-frame simulations."""
    universe = context.get_value("universe")
    if not universe:
        context.fail("missing_universe", "No universe loaded for PBC unwrapping")

    pbc = PbcRepair(universe, context.config)
    report = pbc.run()

    context.record_data("pbc/report", report.to_dict())

    # Warn if jumps detected but unwrapping is disabled
    if report.jumps_detected and not context.config.loader.unwrap_periodic_boundaries:
        context.add_warning(
            "pbc_jumps_detected",
            "Periodic boundary jumps detected. The input structure appears broken across periodic boundaries.",
            details={
                "max_bond_length": report.max_bond_length,
                "bond_jumps": report.bond_jumps,
                "max_backbone_gap": report.max_backbone_gap,
                "backbone_jumps": report.backbone_jumps,
            }
        )

    # Info warning if unwrapping was applied
    if report.unwrapped:
        context.add_warning(
            "pbc_unwrap_applied",
            "Periodic boundary unwrapping was applied to make molecules whole."
        )

    # Warning if unwrapping was enabled but failed
    if context.config.loader.unwrap_periodic_boundaries and report.error:
        context.add_warning(
            "pbc_unwrap_failed",
            f"Periodic boundary unwrapping failed: {report.error}"
        )

    # BH-052 self-check: molecules still split across the box
    if (context.config.loader.unwrap_periodic_boundaries
            and report.unwrap_incomplete):
        context.add_warning(
            "pbc_unwrap_incomplete",
            "Periodic boundary unwrapping did not make molecules whole: "
            "bonded pairs remain above 4 A after unwrapping.",
            details={
                "bonded_pairs_over_4a": report.post_unwrap_bonds_over_4a,
                "post_unwrap_max_bond_length": report.post_unwrap_max_bond_length,
            }
        )

    return StepResult(
        summary={"unwrapped": report.unwrapped, "jumps_detected": report.jumps_detected},
        context_updates={"pbc_report": report}
    )


def _analyze_universe(context):
    """Analyze the loaded universe: segments, fragments, molecules."""
    universe = context.get_value("universe")
    decision = context.get_value("load_decision")
    report = context.get_value("repair_report")

    if not universe:
        context.fail("missing_universe", "No universe loaded for analysis")

    # W3 A6 (BH-047): facade/store construction records one results.json
    # write per segment fragment; defer to <= 1 per 10 s + final flush.
    with _deferred_writes(context.results):
        facade = LoadedUniverse(
            universe=universe,
            decision=decision,
            repair_report=report,
            results=context.results,
            enhanced_nucleic_recognition=(
                context.config.signatures.enhanced_nucleic_acid_recognition
            ),
        )

        store = FragmentStore(facade, context.results)

        context.record_data("molecules/count", len(store.get_all_instances()))
        context.record_data("molecules/unique_count", len(store.get_unique_molecules()))
        context.record_data("molecules/type_counts", store.get_unique_counts_by_type())

    # Record whole-system info
    system = store.get_whole_system_instance()
    context.record_data("molecules/system/atom_count", system.atom_count)

    return StepResult(
        summary={
            "analyzed": True,
            "segments": len(facade.get_segments()),
            "unique_molecules": len(store.get_unique_molecules()),
            "total_fragments": store.get_total_fragment_count(),
        },
        context_updates={"facade": facade, "fragment_store": store}
    )


class _PinnedPropsFacade:
    """OQ-9 routing proxy (2026-10-05): pin per-segment props into the serial
    signature loop so generators see the CURRENT segment's flags.

    Generators resolve segment properties via
    ``facade.get_segment_properties(fragment.segids[0])`` -- for virtual
    minority segments (``SYSTEM__vN``) the fragment's segids[0] is the PARENT
    segid ("SYSTEM"), whose props classify the majority species (protein),
    which made protein-family generators fire on nucleic fragments in the
    serial path (parallel worker mock-facades were already correct). This
    proxy answers get_segment_properties() with the props fetched for the
    driver-loop segment name (virtual or flat); everything else passes
    through to the real facade. For flat segments the pinned props object is
    the very same object today's lookup would return -> byte-invariant.
    """

    __slots__ = ("_real", "_props")

    def __init__(self, real: Any, props: Any) -> None:
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_props", props)

    def get_segment_properties(self, segment_name: str) -> Any:
        return self._props

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


def _pinned_props_facade(facade: Any, segment_name: str) -> Any:
    """Wrap facade so this segment's props win (see _PinnedPropsFacade).
    Falls back to the unwrapped facade when props are unavailable."""
    try:
        props = facade.get_segment_properties(segment_name)
    except Exception:
        return facade
    return _PinnedPropsFacade(facade, props)


# B1 (BH-042): polymer-typed segments route to SEQUENCE/STRUCTURE
# resolvers only — chemistry signatures on protein/nucleic fragments
# waste the whole identify stage on impossible lookups.
_POLYMER_TYPES = frozenset({"protein", "nucleic"})
_POLYMER_SUPPRESSED_GENERATORS = frozenset({
    "smiles", "smiles_not_sanitized", "selfies", "inchi_key"})


def _molecule_type_value(instance) -> str:
    """MoleculeType-safe text: str(Enum) is 'MoleculeType.X', not the
    payload, so unwrap .value when present."""
    m = getattr(instance, "molecule_type", "") or ""
    m = getattr(m, "value", m)
    return str(m)


def _instance_residue_count(instance) -> int | None:
    """Residue count for a MoleculeInstance (best effort)."""
    resids = getattr(instance, "resids", None)
    if resids:
        try:
            return len(set(resids))
        except TypeError:
            pass
    ri = getattr(instance, "residue_indices", None)
    if ri:
        try:
            return len(set(ri))
        except TypeError:
            pass
    return None


def _polymer_chemistry_suppressed(instance, generator_name) -> bool:
    """True when generator_name must not run for a POLYMER-typed segment
    (B1/BH-042).

    W3.1 item 6: SHORT polymer-typed segments (<= 5 residues — e.g. a
    ligand glycine zwitterion, C19, or a small peptide) keep their
    chemistry signatures; the suppression targets real polymers, whose
    sequence/structure resolvers are the right tool."""
    if generator_name not in _POLYMER_SUPPRESSED_GENERATORS:
        return False
    if _molecule_type_value(instance) not in _POLYMER_TYPES:
        return False
    rc = _instance_residue_count(instance)
    if rc is not None and rc <= 5:
        return False  # short polymer: amino-acid/small-peptide ligand
    return True


def _chemistry_size_skipped(atom_count, generated_keys, cap):
    """bughunt BH-032: True when a molecule above the chemistry atom cap
    produced no SMILES signature (the skip used to be completely silent —
    M12 enramycin, 309 atoms vs the 250 cap, no message anywhere)."""
    if not atom_count or atom_count <= cap:
        return False
    return not any(k.split("[")[0] in ("smiles", "smiles_not_sanitized")
                   for k in generated_keys)



def _deferred_writes(results):
    """Deferred-save window (W3 A6) when the results store supports it;
    a null context otherwise (test fakes / lightweight contexts)."""
    cm = getattr(results, "deferred_saves", None)
    if callable(cm):
        return cm()
    import contextlib
    return contextlib.nullcontext()


# W3 A6 (BH-047): generators whose output is per-copy by construction
# (they embed the segment/chain identity). Everything else is shared
# across copies of the same molecule.
_PER_COPY_GENERATORS = {"mmcif", "name_chain", "name_segment"}


def _base_generator_name(out_key: str) -> str:
    """'fasta_map_protein[A]' -> 'fasta_map_protein'."""
    return out_key.split("[", 1)[0]


def _snapshot_group_key(snapshot) -> tuple:
    """Strengthened per-unique key for signature generation (W3 A6):
    bond topology + atom names + elements + residue names. Two copies of
    the same molecule differ only in placement, never in these."""
    try:
        # W3.1-3 (A6): remap universe-level bond indices to FRAGMENT-LOCAL
        # positions — two physical copies of one molecule must share the
        # key (universe-level indices made the dedup inert).
        pos_of = {int(ix): i for i, ix in
                  enumerate(snapshot.atom_indices or [])}
        bonds = tuple(sorted(
            tuple(sorted((pos_of[int(a)], pos_of[int(b)])))
            for a, b in (snapshot.bonds or [])
            if int(a) in pos_of and int(b) in pos_of))
    except Exception:
        bonds = ()
    return (
        getattr(snapshot, "molecule_type", None),
        getattr(snapshot, "atom_count", None),
        getattr(snapshot, "residue_count", None),
        tuple(getattr(snapshot, "names", ())),
        tuple(getattr(snapshot, "elements", ())),
        bonds,
        tuple(getattr(snapshot, "resnames", ())),
        # W3.1-3 (A6): stereo signature — R vs S split into different
        # unique groups; copies of one enantiomer share the key.
        tuple(getattr(snapshot, "stereo_tags", ()) or ()),
    )


def _generate_signatures(context):
    """Generate signatures for all segments with optional parallelism."""
    from ..signatures.registry import get_default_generators
    from ..signatures.snapshot import build_signature_snapshot, SegmentSignatureSnapshot
    from ..executor.parallel import run_with_process_pool
    from .workers import _generate_signatures_worker
    
    facade = context.get_value("facade")
    store = context.get_value("fragment_store")

    if not facade or not store:
        context.fail("missing_facade", "No facade available for signature generation")

    # W3.1 P24 follow-up / W3 BH-053: reset the run-level DBO ladder
    # cap, scoped to THIS run (threaded callers share one interpreter;
    # runs must not drain one counter). The serial in-process path
    # shares this module state (the process-pool workers are
    # spawn-fresh and start at zero).
    from ..signatures.generators._perceive_cache import (
        dbo_run_budget_reset, set_dbo_run_id)
    set_dbo_run_id(getattr(context.results, "run_id", "") or "")
    dbo_run_budget_reset()

    # Get all instances from store
    all_instances = store.get_all_instances()

    # Create a mapping from segment_name to instance (EVERY member
    # segment, not just the representative - copies need it at merge).
    segment_to_instance = {}
    for inst in all_instances:
        for seg_name in (inst.segment_ids or []):
            segment_to_instance.setdefault(seg_name, inst)

    # Build snapshots for all segments
    snapshots = []
    snapshot_by_segment = {}
    for segment_name in sorted(facade.get_segments()):
        fragment = facade.get_fragment(segment_name)
        instance = segment_to_instance.get(segment_name)

        if instance is None:
            logger.warning(f"No MoleculeInstance found for segment {segment_name}, skipping signatures")
            continue

        try:
            snapshot = build_signature_snapshot(segment_name, fragment, instance, facade)
            snapshots.append(snapshot)
            snapshot_by_segment[segment_name] = snapshot
        except Exception as e:
            logger.warning(f"Failed to build snapshot for {segment_name}: {e}")
            continue

    if not snapshots:
        return StepResult(summary={"generated": True, "segments": 0, "signatures": 0})

    # W3 A6 (BH-047): group segments by the strengthened uniqueness key
    # and generate ONCE per unique fragment group (F14: 4x instead of
    # 2952x), then copy results to the copies. Only mmcif/name_chain/
    # name_segment differ per copy and are recomputed at merge time.
    groups = {}
    ordered_keys = []
    for snapshot in snapshots:
        key = _snapshot_group_key(snapshot)
        if key not in groups:
            groups[key] = []
            ordered_keys.append(key)
        groups[key].append(snapshot.segment_name)
    reps = []
    group_members = {}
    for key in ordered_keys:
        members = groups[key]
        rep = members[0]
        reps.append(snapshot_by_segment[rep])
        group_members[rep] = members
    
    # Convert config to dict for workers
    config_dict = context.config.to_dict()
    deadline = budget_deadline(context)
    if deadline is not None:
        config_dict["_stage_deadline_epoch"] = deadline
    # W3 BH-053: the run-scoped DBO ladder budget follows the run into
    # the process-pool workers too (defensive: pools are spawn-fresh
    # today, but the budget must not silently belong to another run).
    config_dict["_dbo_run_id"] = getattr(context.results, "run_id", "") or ""

    generators = get_default_generators(context.config.signatures)

    # Decide whether to use parallel execution (representatives only)
    use_parallel = (
        context.config.executor.signatures_parallel and
        len(reps) > 1
    )

    max_workers = context.config.executor.n_threads

    results = None
    budget_hit = False
    if use_parallel:
        # Run in process pool
        items = [(s.__dict__, config_dict) for s in reps]
        results = run_with_process_pool(max_workers, _generate_signatures_worker, items)
    else:
        # Direct serial execution: use real objects, skip snapshot reconstruction
        results = []
        _spin_dbg = os.environ.get("SPIN_DEBUG") == "1"
        rep_names = [s.segment_name for s in reps]
        for segment_name in rep_names:
            if _budget_exceeded(context):
                budget_hit = True
                logger.warning(f"generate_signatures: stage time budget exceeded at segment {segment_name}; partial output")
                break
            instance = segment_to_instance.get(segment_name)
            fragment = facade.get_fragment(segment_name)
            if instance is None:
                continue
            # OQ-9: route THIS segment's props (virtual minority or flat) into
            # generator applicability/generation -> serial == parallel parity.
            segment_facade = _pinned_props_facade(facade, segment_name)
            generated = {}
            attempted = []
            errors = []
            for generator in generators:
                # B1 (BH-042): polymers route to sequence/structure
                # resolvers only — never run chemistry generators on them.
                if generator.name in _POLYMER_SUPPRESSED_GENERATORS and \
                        _polymer_chemistry_suppressed(instance, generator.name):
                    continue
                # B-07 (red-team 4.3): budget gate INSIDE the segment as well —
                # previously checked only between segments, so one heavy
                # segment ran unbounded. Generators that already STARTED still
                # finish (bounded by their own guards), later ones are skipped.
                if _budget_exceeded(context):
                    budget_hit = True
                    logger.warning(
                        f"generate_signatures: stage time budget exceeded mid-segment "
                        f"{segment_name} before {generator.name}; skipping remaining generators")
                    break
                _g_t0 = time.time()
                try:
                    if generator.is_applicable(instance, fragment, segment_facade):
                        attempted.append(generator.name)
                        if _spin_dbg:
                            print(f"[SPIN] {segment_name}/{generator.name} START", flush=True)
                        sig = generator.generate(instance, fragment, segment_facade)
                        if _spin_dbg:
                            print(f"[SPIN] {segment_name}/{generator.name} DONE {time.time()-_g_t0:.1f}s", flush=True)
                        if isinstance(sig, dict):
                            # B-05 (red-team 4.6): per-chain fasta emission
                            for _label, _val in sig.items():
                                if _val:
                                    generated[f"{generator.name}[{_label}]"] = _val
                        elif sig is not None:
                            generated[generator.name] = sig
                        else:
                            errors.append({"generator": generator.name, "error": "Generation returned None"})
                except Exception as exc:
                    errors.append({"generator": generator.name, "error": str(exc)})
                    continue
            results.append({
                "segment_name": segment_name,
                "generated": generated,
                "attempted": attempted,
                "errors": errors,
                # B-10 (red-team 4.4) h_inferred; B-08 (red-team 4.7)
                # xbond_capped: cross-fragment bonds are H-capped before
                # perception (covalent ligands/heme/glycans)
                "flags": _segment_flags(fragment),
            })
    
    # Merge results into context.results in main thread.
    # W3 A6 (BH-047): each representative expands to its whole unique
    # group; per-copy generators (mmcif/name_chain/name_segment) are
    # recomputed per member; all writes go through a deferred-save
    # window (<= 1 write / 10 s + final flush - F14 wrote 41.6k times,
    # 6146 s for 4.2 s of chemistry), and the stage budget is checked
    # INSIDE the merge loop (the generation loop ends long before the
    # unbounded merge used to).
    if budget_hit:
        _grant_merge_grace(context)  # W3.1-3: keep the partials we paid for

    generated_count = 0
    _atom_cap = context.config.signatures.smiles_maximum_number_of_atoms
    _per_copy_gens = [g for g in generators if g.name in _PER_COPY_GENERATORS]
    _size_skip_warned: set = set()
    with _deferred_writes(context.results):
        for result in results:
            if result is None:
                continue

            rep_name = result["segment_name"]

            # Record warnings from errors (once per representative)
            for error in result.get("errors", []):
                gen_name = error.get("generator", "unknown")
                error_msg = error.get("error", "unknown error")
                context.add_warning("signature_generator_failed", f"{gen_name}: {error_msg}",
                                    details={"segment": rep_name, "generator": gen_name,
                                             "service": gen_name})

            for member_name in group_members.get(rep_name, [rep_name]):
                if _budget_exceeded(context):
                    budget_hit = True
                    logger.warning(
                        f"generate_signatures: stage time budget exceeded during merge "
                        f"at {member_name}; partial output")
                    break

                instance = segment_to_instance.get(member_name)
                fragment = facade.get_fragment(member_name)

                if member_name == rep_name:
                    gen_map = dict(result.get("generated", {}))
                    attempted = list(result.get("attempted") or [])
                    errors = list(result.get("errors", []))
                else:
                    # shared chemistry from the representative
                    gen_map = {
                        k: v for k, v in result.get("generated", {}).items()
                        if _base_generator_name(k) not in _PER_COPY_GENERATORS
                    }
                    attempted = [a for a in (result.get("attempted") or [])
                                 if a not in _PER_COPY_GENERATORS]
                    errors = list(result.get("errors", []))
                    # per-copy outputs recomputed for THIS member
                    if instance is not None and fragment is not None:
                        member_facade = _pinned_props_facade(facade, member_name)
                        for gen_obj in _per_copy_gens:
                            try:
                                if gen_obj.is_applicable(instance, fragment, member_facade):
                                    attempted.append(gen_obj.name)
                                    sig = gen_obj.generate(instance, fragment, member_facade)
                                    if isinstance(sig, dict):
                                        for _label, _val in sig.items():
                                            if _val:
                                                gen_map[f"{gen_obj.name}[{_label}]"] = _val
                                    elif sig is not None:
                                        gen_map[gen_obj.name] = sig
                            except Exception:
                                continue

                for gen_name, sig in gen_map.items():
                    context.results.set_data(f"signatures/{member_name}/generated/{gen_name}", sig)
                    generated_count += 1

                if attempted:
                    context.results.set_data(f"signatures/{member_name}/attempted", attempted)

                flags = _segment_flags(fragment) if fragment is not None else result.get("flags")
                if flags:
                    context.results.set_data(f"signatures/{member_name}/flags", flags)

                # bughunt BH-032: a molecule above the chemistry atom cap
                # got no SMILES/InChI SILENTLY - make the skip visible.
                # B2 (BH-043): only meaningful for NON-polymers (polymers
                # have no chemistry signatures by design, B1) and at most
                # once per segment.
                _inst = segment_to_instance.get(member_name)
                if (_inst is not None
                        and _molecule_type_value(_inst) not in _POLYMER_TYPES
                        and member_name not in _size_skip_warned
                        and _chemistry_size_skipped(
                            getattr(_inst, "atom_count", None),
                            list(gen_map),
                            _atom_cap)):
                    _size_skip_warned.add(member_name)
                    context.add_warning(
                        "chemistry_skipped_size",
                        f"{member_name}: {_inst.atom_count} atoms exceeds the chemistry "
                        f"atom limit ({_atom_cap}); SMILES/InChI signatures skipped "
                        "(formula and residue-name signatures still generated)",
                        details={"segment": member_name,
                                 "atom_count": _inst.atom_count,
                                 "limit": _atom_cap},
                    )

                # F-N1e: persist (bounded) generation errors for postmortem visibility
                _sig_errs = bounded_stage_errors(errors)
                if _sig_errs:
                    context.results.set_data(f"stage_errors/signatures/{member_name}", _sig_errs)

            if budget_hit:
                break

    if budget_hit:
        context.add_warning(
            "stage_time_budget",
            "generate_signatures exceeded its time budget; proceeding with partial signatures",
        )
    return StepResult(
        summary={"generated": True, "segments": len(snapshots), "signatures": generated_count,
                 "partial": budget_hit}
    )


# --- W3 A7 (BH-046): content-key grouping for identification --------------

def _identify_group_key(fragment_name: str, generated: dict):
    """Group key for identical-segment identification (W3 A7).

    polymer       -> ("polymer", canonical fasta sequence)
    small molecule-> ("small", inchi_key|canonical SMILES — tautomer-safe)
    formula-only  -> ("small_formula", formula|fp)
    water         -> None (skipped: nothing worth resolving)
    no chemistry  -> ("all_other", fragment_name) SINGLETON (W3.1 item 9:
                      the name-based fallback merged unrelated species)
    """
    from ..molecules.instances import WATER_RESNAMES
    # W3.1 item 9 (A7): the water skip must fire on the REAL water
    # signatures — name_molecule carries the common name ("water"),
    # the resname carries HOH/SOL/TIP3/..., and the formula is H2O
    # (the heavy formula alone, "O", is never enough). The old check
    # matched only resnames through name_molecule/name_segment, so the
    # skip never fired (C05/P04 water was resolved as a small molecule).
    nm = str(generated.get("name_molecule")
             or generated.get("name_segment") or "").strip()
    rn = str(generated.get("resname") or "").strip()
    formula = str(generated.get("molecular_formula") or "").strip()
    if ((nm and (nm.upper() in WATER_RESNAMES or nm.upper() == "WATER"))
            or (rn and rn.upper() in WATER_RESNAMES)
            or formula in ("H2O", "D2O")):
        return None
    seqs = []
    for g in ("fasta_map_protein", "fasta_map_nucleic",
              "fasta_resname_protein", "fasta_resname_nucleic"):
        seq = generated.get(g)
        if isinstance(seq, str) and len(seq) >= 3:
            seqs.append(seq)
        elif isinstance(seq, dict):
            seqs.extend(v for _l, v in sorted(seq.items())
                        if isinstance(v, str) and len(v) >= 3)
    if not seqs:
        # W3.1-1b / item 9 (A7 bracket keys): a union representative
        # carries per-chain FLATTENED keys (fasta_map_protein[A], ...) —
        # match them; a union rep must never fall through to
        # ("ion", name).
        import re as _re
        seqs.extend(v for _k, v in sorted(generated.items())
                    if isinstance(v, str) and len(v) >= 3 and _re.fullmatch(
                        r"fasta_(map|resname)_(protein|nucleic)\[.+\]", _k))
    if seqs:
        uniq = sorted(set(seqs))
        if len(seqs) == 1:
            return ("polymer", seqs[0])
        return ("polymer", "|".join(uniq))
    ik = generated.get("inchi_key")
    if ik:
        # W3.1 item 9 (A7): tautomer-safe key — the standard InChIKey
        # MERGES tautomers (C18: 2-pyridone vs 2-hydroxypyridine share
        # UBQKCCHYAOITMY-UHFFFAOYSA-N but had different top-1 hits
        # pre-W3); the canonical SMILES disambiguates them. True copies
        # (identical payloads) still share the key.
        smi = str(generated.get("smiles")
                  or generated.get("smiles_not_sanitized")
                  or "").strip()
        return ("small", f"{ik}|{smi}" if smi else str(ik))
    hf = generated.get("molecular_formula_heavy")
    if hf:
        return ("small_formula", f"{hf}|{generated.get('fingerprint', '')}")
    # W3.1 item 9 (A7): the name-based fallback merged unrelated species
    # that happen to share a display name — the fallback is now a
    # SINGLETON per fragment. Real ions carry molecular_formula_heavy
    # (C13/C16/C17) and still merge through the formula branch above;
    # only species with NO chemistry and NO formula land here, and
    # merging those by name was the hazard.
    return ("all_other", fragment_name)


def _identify_group_order(kind: str, key: str) -> tuple:
    """Polymers first (longest sequence first), then small molecules,
    then ions, then unclassified singletons (W3 A7 step 3)."""
    rank = {"polymer": 0, "small": 1, "small_formula": 2, "ion": 3}.get(kind, 4)
    return (rank, -len(key), key)


def _group_segments(items_fragments: list) -> tuple:
    """Split fragments into resolution groups (W3 A7 steps 1-2).

    Returns (reps, member_to_rep, rep_to_group): reps = ordered
    representative fragment names; member_to_rep = skipped members ->
    rep; rep_to_group = list of (rep, members, group_key).
    """
    groups: dict = {}
    for fragment_name, generated in items_fragments:
        gk = _identify_group_key(fragment_name, generated)
        if gk is None:
            continue  # water: skipped entirely, never unresolved-reported
        groups.setdefault(gk, []).append(fragment_name)
    ordered = sorted(groups.items(),
                     key=lambda kv: _identify_group_order(kv[0][0], kv[0][1]))
    reps, member_to_rep, rep_to_group = [], {}, []
    for gk, members in ordered:
        members = sorted(members)
        rep = members[0]
        reps.append(rep)
        rep_to_group.append((rep, members, gk))
        for m in members[1:]:
            member_to_rep[m] = rep
    return reps, member_to_rep, rep_to_group


def _propagate_group_identifiers(results, rep_to_group) -> int:
    """Copy each group's rep identifiers payload to its members, with a
    _shared_with marker (W3 A7 step 2)."""
    copied = 0
    for rep, members, _gk in rep_to_group:
        if len(members) < 2:
            continue
        blob = results.get_data(f"identifiers/{rep}")
        if not blob:
            continue
        shared = dict(blob)
        shared["_shared_with"] = rep
        for member in members[1:]:
            results.set_data(f"identifiers/{member}", shared)
            copied += 1
    return copied


def _identify_molecules(context):
    """Identify molecules from generated signatures with optional parallelism."""
    from ..signatures.registry import get_signature_type_map
    from ..executor.parallel import run_with_thread_pool
    from .workers import _identify_molecules_worker
    
    facade = context.get_value("facade")
    if not facade:
        context.fail("missing_facade", "No facade available for identification")

    # W3.1 item 4 (A9): loud once-per-run notice when structure search
    # will be silently skipped (no adhoc dir + no registry uuid).
    _maybe_warn_structure_search(context, context.config)

    # Get signature type map
    sig_type_map = get_signature_type_map(context.config.signatures)
    
    # Get all segments from signatures data
    signatures_data = context.results.get_data("signatures")
    if not signatures_data or not isinstance(signatures_data, dict):
        logger.warning("No signatures data found in results")
        return StepResult(summary={"identified": True})
    
    # Defensive: log warnings for missing generator entries
    for fragment_name in signatures_data.keys():
        fragment_data = signatures_data[fragment_name]
        if isinstance(fragment_data, dict):
            generated = fragment_data.get('generated', {})
            if isinstance(generated, dict):
                for gen_name in generated.keys():
                    if gen_name not in sig_type_map:
                        logger.warning(f"Signature type map missing entry for '{gen_name}'")
    
    # Build work items:
    #   parallel: (fragment_name, valid_sigs, config_dict, sig_type_map,
    #              existing_identifiers)  # F-15: seed for overwrite_existing parity
    #   serial:   (fragment_name, valid_sigs)
    items_parallel = []
    items_serial = []
    items_fragments = []   # A7: (fragment, generated) for grouping
    valid_sigs_by_name: dict = {}
    for fragment_name in sorted(signatures_data.keys()):
        generated = signatures_data[fragment_name].get("generated", {})
        if not generated:
            continue

        # Filter out empty signatures
        valid_sigs = {k: v for k, v in generated.items() if v}
        if not valid_sigs:
            continue

        items_fragments.append((fragment_name, generated))
        # W3.1 item 9 (A7): keep every fragment's valid signatures for
        # the member-retry path (items_serial below is filtered to
        # group representatives).
        valid_sigs_by_name[fragment_name] = valid_sigs
        # F-15: pass the fragment's already-persisted identifiers blob so the
        # parallel worker (which resolves into a temp ResultsManager) can skip
        # present resolvers exactly like the serial path does.
        existing_ids = context.results.get_data(f"identifiers/{fragment_name}") or {}
        items_parallel.append((fragment_name, valid_sigs, context.config.to_dict(), sig_type_map, existing_ids))
        items_serial.append((fragment_name, valid_sigs))

    if not items_parallel:
        return StepResult(summary={"identified": True})

    # A7 (BH-046): resolve IDENTICAL segments once (P23: identical GroEL
    # chains got three DIFFERENT assignments per-copy; F14: 2952 segments
    # resolved per-copy in a projected 17 h). Group by content key, keep
    # the representative; members inherit after resolution.
    group_reps, member_to_rep, rep_to_group = _group_segments(items_fragments)
    if member_to_rep:
        logger.info(
            "identify_molecules: %d segments -> %d resolution groups",
            len(items_fragments), len(group_reps))
        group_reps_set = set(group_reps)
        items_parallel = [it for it in items_parallel
                          if it[0] in group_reps_set]
        items_serial = [it for it in items_serial if it[0] in group_reps_set]
    # W3.1 item 9 (A7): APPLY the group ordering — polymers first
    # (longest sequence first), then small molecules, then formula-keyed
    # species, then singletons. The ordering was computed in
    # _group_segments but never applied: the resolution order stayed
    # alphabetical, so a stage budget cut could starve polymers while
    # ions resolved first.
    if group_reps:
        _rep_rank = {name: i for i, name in enumerate(group_reps)}
        _tail = len(_rep_rank)
        items_parallel.sort(key=lambda it: _rep_rank.get(it[0], _tail))
        items_serial.sort(key=lambda it: _rep_rank.get(it[0], _tail))
    
    # Decide whether to use parallel execution
    use_parallel = (
        context.config.executor.identifiers_parallel and 
        len(items_parallel) > 1
    )
    
    max_workers = context.config.executor.n_threads
    
    # Propagate the stage deadline into worker configs
    deadline = budget_deadline(context)
    if deadline is not None:
        items_parallel = [
            (fn, vs, {**cfg, "_stage_deadline_epoch": deadline} if isinstance(cfg, dict) else cfg, stm, ex)
            for (fn, vs, cfg, stm, ex) in items_parallel
        ]

    results = None
    budget_hit = False
    if use_parallel:
        # Run in thread pool
        results = run_with_thread_pool(max_workers, _identify_molecules_worker, items_parallel)
    else:
        # Direct serial execution: use real manager (writes directly to context.results)
        from ..identification.registry import get_default_resolvers, IdentifierRegistry
        from ..identification.cache_manager import ResolverCache
        from ..identification.resolution_manager import IdentifierResolutionManager
        from ..signatures.registry import get_signature_type_map

        sig_type_map = get_signature_type_map(context.config.signatures)
        resolvers = get_default_resolvers(context.config)
        registry = IdentifierRegistry(resolvers)
        cache = ResolverCache(context.config)
        manager = IdentifierResolutionManager(registry, context.config, signature_type_map=sig_type_map)

        # W3 A6 (BH-047): resolve() writes per (segment, generator, hit) -
        # defer saves across the serial resolve loop.
        results = []
        with _deferred_writes(context.results):
            for fragment_name, valid_sigs in items_serial:
                if _budget_exceeded(context):
                    budget_hit = True
                    logger.warning(f"identify_molecules: stage time budget exceeded at fragment {fragment_name}; partial output")
                    break
                fragment_result = {"fragment_name": fragment_name, "results": {}, "errors": []}
                for generator_name, signature in valid_sigs.items():
                    if _budget_exceeded(context):
                        budget_hit = True
                        logger.warning(f"identify_molecules: stage time budget exceeded at {fragment_name}/{generator_name}; partial output")
                        break
                    # Collect errors from this resolution
                    resolver_errors = []
                    hits_found = manager.resolve(
                        results=context.results,
                        segment=fragment_name,
                        signature_generator_name=generator_name,
                        signature=signature,
                        cache=cache,
                        working_directory=str(context.working_directory),
                        errors=resolver_errors,
                        deadline_epoch=budget_deadline(context),
                    )
                    # Add resolver errors to fragment_result
                    fragment_result["errors"].extend(resolver_errors)
                # In serial mode, manager.resolve() writes directly to context.results
                # so we just return an empty results dict and errors
                results.append(fragment_result)

    # Merge results into context.results in main thread
    # W3 A6 (BH-047): deferred-save window (parallel workers return one
    # entry per segment per generator here).
    if budget_hit:
        _grant_merge_grace(context)  # W3.1-3: keep the partials we paid for

    with _deferred_writes(context.results):
        for result in results:
            if result is None:
                continue
            if _budget_exceeded(context):
                budget_hit = True
                logger.warning("identify_molecules: stage time budget exceeded during merge; partial output")
                break

            fragment_name = result["fragment_name"]

            # Record warnings from errors
            for error in result.get("errors", []):
                resolver_name = error.get("resolver", "unknown")
                gen_name = error.get("generator", "unknown")
                error_msg = error.get("error", "unknown error")
                context.add_warning("identifier_resolver_failed", f"{resolver_name} ({gen_name}): {error_msg}",
                                    details={"segment": fragment_name, "service": resolver_name,
                                             "generator": gen_name})

            # F-N1e: persist (bounded) resolution errors for postmortem visibility
            _ident_errs = bounded_stage_errors(result.get("errors", []))
            if _ident_errs:
                context.results.set_data(f"stage_errors/identifiers/{fragment_name}", _ident_errs)

            for path, value in result["results"].items():
                context.results.set_data(path, value)
    
    # A7 (BH-046) / W3.1-3: members inherit the group's identifiers (one
    # payload per group; _shared_with records the representative name).
    # Runs INSIDE the deferred-writes window — per-member flushes were the
    # slow path (F14 propagation target < 5 s).
    with _deferred_writes(context.results):
        _propagate_group_identifiers(context.results, rep_to_group)

    # W3.1 item 9 (A7): retry with the next member when the
    # representative fails — a transient resolver failure on one copy
    # must not unresolve its whole group (audit: "nothing retries with
    # another member when the representative fails"). Bounded by the
    # stage budget; the first member whose resolution produces
    # identifiers is promoted to the group's source.
    if (not _budget_exceeded(context)
            and any(
                len(members) > 1
                and context.results.get_data(f"identifiers/{rep}") is None
                for rep, members, _gk in rep_to_group)):
        from ..identification.registry import get_default_resolvers, IdentifierRegistry
        from ..identification.cache_manager import ResolverCache
        from ..identification.resolution_manager import IdentifierResolutionManager
        from ..signatures.registry import get_signature_type_map as _gstm
        _retry_mgr = IdentifierResolutionManager(
            IdentifierRegistry(get_default_resolvers(context.config)),
            context.config,
            signature_type_map=_gstm(context.config.signatures))
        _retry_cache = ResolverCache(context.config)
        promoted = []
        with _deferred_writes(context.results):
            for rep, members, _gk in rep_to_group:
                if len(members) < 2:
                    continue
                if _budget_exceeded(context):
                    budget_hit = True
                    logger.warning(
                        "identify_molecules: retry abandoned at group of "
                        f"{rep}; stage time budget exceeded")
                    break
                if context.results.get_data(f"identifiers/{rep}") is not None:
                    continue  # representative succeeded after all
                src = None
                for member in members[1:]:
                    vs = valid_sigs_by_name.get(member) or {}
                    if not vs:
                        continue
                    for gen_name, sig_value in vs.items():
                        if _budget_exceeded(context):
                            budget_hit = True
                            break
                        _retry_errs: list = []
                        _retry_mgr.resolve(
                            results=context.results,
                            segment=member,
                            signature_generator_name=gen_name,
                            signature=sig_value,
                            cache=_retry_cache,
                            working_directory=str(context.working_directory),
                            errors=_retry_errs,
                            deadline_epoch=budget_deadline(context),
                        )
                    if context.results.get_data(
                            f"identifiers/{member}") is not None:
                        src = member
                        break
                if src is not None:
                    logger.info(
                        "identify_molecules: representative %s failed; "
                        "promoted member %s for its group", rep, src)
                    promoted.append(
                        (src, [src] + [m for m in members if m != src], _gk))
            if promoted:
                _propagate_group_identifiers(context.results, promoted)

    # A7 (BH-046): report budget-cut/dropped GROUPS, not fragments — a
    # budget cut can never split a group (reps resolve atomically, members
    # only inherit).
    unresolved_groups = []
    for rep, members, gk in rep_to_group:
        if context.results.get_data(f"identifiers/{rep}") is None:
            unresolved_groups.append({
                "representative": rep,
                "members": members,
                "kind": gk[0],
            })
    if unresolved_groups:
        context.results.set_data("identification/unresolved_groups",
                                 unresolved_groups)
        context.add_warning(
            "identification_groups_unresolved",
            f"{len(unresolved_groups)} identification group(s) unresolved "
            f"({sum(len(g['members']) for g in unresolved_groups)} segment(s))",
        )

    if budget_hit:
        context.add_warning(
            "stage_time_budget",
            "identify_molecules exceeded its time budget; proceeding with partial identifications",
        )
    return StepResult(
        summary={"identified": True, "partial": budget_hit,
                 "groups": len(rep_to_group)}
    )


def _verify_results(context):
    """Verify identification results with optional parallelism."""
    from ..executor.parallel import run_with_thread_pool
    from .workers import _verify_results_worker
    from ..verification.base import clear_run_memo
    
    facade = context.get_value("facade")
    if not facade:
        context.fail("missing_facade", "No facade available for verification")
    
    # W3.2 A7: fresh fetch memo per run (fetch results, including negative
    # ones, are memoized per (fetcher class, ident type, identifier) — the
    # firewalled workstation burned ~5 min per repeated InChIKey fetch).
    clear_run_memo()
    
    # Get all segments from identifiers data
    identifiers_data = context.results.get_data("identifiers")
    if not identifiers_data or not isinstance(identifiers_data, dict):
        return StepResult(summary={"verified": True})
    
    # W3.2 A7: verify once per resolution GROUP. identify_molecules copies
    # each group representative's identifiers to its members with a
    # ``_shared_with`` marker; verification runs only for representatives
    # and ungrouped segments, and the output is copied to the members the
    # same way (with their own ``_shared_with`` marker). A budget cut
    # therefore leaves whole groups unverified — never part of one.
    # (Production shape at b954adc33: P23 = 4 identify groups but 35
    # verify calls; the budget cut at D_1 left GroES O–U unanswered.)
    member_to_rep: dict[str, str] = {}
    for segment in identifiers_data:
        sd = identifiers_data[segment]
        if isinstance(sd, dict) and sd.get("_shared_with"):
            rep = str(sd["_shared_with"])
            if rep in identifiers_data:
                member_to_rep[segment] = rep
    verify_targets = [s for s in sorted(identifiers_data) if s not in member_to_rep]
    
    # Read signatures data once
    signatures_data = context.results.get_data('signatures') or {}
    
    # Build work items: (segment, segment_identifiers_data, config_dict,
    # segment_signatures_data, segment_properties_data)
    # segment_properties_data carries universe/segments/<seg>/properties so
    # universe-aware verification rules (element ground truth) see real facts —
    # the worker builds a MINIMAL temp manager and would otherwise miss them.
    # segments_summary does the same for fragments/segments (water ground-truth
    # rule, v3.140) — built once here so every worker sees the full type list.
    deadline = budget_deadline(context)
    segments_summary = context.results.get_data("fragments/segments") or None
    items = []
    for segment in verify_targets:
        segment_data = identifiers_data[segment]
        cfg = context.config.to_dict()
        if deadline is not None:
            cfg["_stage_deadline_epoch"] = deadline
        seg_props = context.results.get_data(f"universe/segments/{segment}/properties")
        items.append((segment, segment_data, cfg, signatures_data.get(segment), seg_props, segments_summary))

    if not items:
        return StepResult(summary={"verified": True})

    # Decide whether to use parallel execution
    use_parallel = (
        context.config.executor.verification_parallel and
        len(items) > 1
    )

    max_workers = context.config.executor.n_threads

    results = None
    budget_hit = False
    if use_parallel:
        # Run in thread pool
        results = run_with_thread_pool(max_workers, _verify_results_worker, items)
    else:
        # Run serially using same worker function
        results = []
        for item in items:
            if _budget_exceeded(context):
                budget_hit = True
                logger.warning(f"verify_results: stage time budget exceeded at segment {item[0]}; partial output")
                break
            result = _verify_results_worker(item)
            results.append(result)
    
    # Merge results into context.results in main thread
    # W3 A6 (BH-047): deferred-save window around per-segment writes.
    with _deferred_writes(context.results):
        for result in results:
            if result is None:
                continue
        
            segment = result["segment"]
            verified_hits = result["verified_hits"]
            # v3.143 (red-team E-01/D-04): the worker surfaces budget cuts on the
            # parallel path as partial=True; fold into the step-level flag.
            if result.get("partial"):
                budget_hit = True
        
            # Record warnings from errors
            for error in result.get("errors", []):
                error_msg = error.get("error", "unknown error")
                context.add_warning("verification_failed", f"{segment}: {error_msg}",
                                    details={"segment": segment})
        
            context.results.set_data(f"verification/{segment}/verified_hits", verified_hits)
            # v3.142 (Phase 4): per-segment class sizes. The parallel worker path
            # discards the per-segment temp ResultsManager (only hits return), so
            # verify_all's own additive writes never reach the final results.json —
            # the step must persist them itself from the returned hit dicts.
            try:
                class_sizes: dict[str, int] = {}
                for h in verified_hits:
                    cid = h.get("equivalence_class_id")
                    if h.get("is_verified") and cid:
                        class_sizes[cid] = class_sizes.get(cid, 0) + 1
                context.results.set_data(f"verification/{segment}/class_sizes", class_sizes)
            except Exception:
                logger.warning("verify_results: class_sizes persist failed (additive only)",
                               exc_info=True)

    # W3.2 A7: members inherit their group representative's verification
    # output — identical content means identical verification. Runs inside
    # its own deferred-writes window (same pattern as the rep merge above).
    if member_to_rep:
        with _deferred_writes(context.results):
            for member, rep in sorted(member_to_rep.items()):
                hits = context.results.get_data(f"verification/{rep}/verified_hits")
                if hits is None:
                    continue  # representative unverified (budget cut) — the
                    # group stays entirely unverified, never partially copied
                context.results.set_data(
                    f"verification/{member}/verified_hits", hits)
                sizes = context.results.get_data(
                    f"verification/{rep}/class_sizes")
                if sizes is not None:
                    context.results.set_data(
                        f"verification/{member}/class_sizes", sizes)
                context.results.set_data(
                    f"verification/{member}/_shared_with", rep)

    # v3.142 (Phase 3): composition provenance — identical dict verify_all
    # writes; the step re-persists it on the REAL results manager because the
    # worker's temp-manager write is discarded in the parallel path.
    try:
        from ..verification.manager import build_confidence_meta
        context.results.set_data("verification/_meta",
                                 build_confidence_meta(context.config.verification))
        # red-team wave-2 (item 1c): aggregate counted annotation-scorer
        # failures forwarded by the workers (additive).
        ann_scorer_errors: dict[str, int] = {}
        for result in results or []:
            if not result:
                continue
            for ident_type, n in (result.get("annotation_scorer_errors") or {}).items():
                ann_scorer_errors[ident_type] = ann_scorer_errors.get(ident_type, 0) + n
        if ann_scorer_errors:
            context.results.set_data("verification/_meta/annotation_scorer_errors",
                                     ann_scorer_errors)
    except Exception:
        logger.warning("verify_results: confidence meta persist failed (additive only)",
                       exc_info=True)

    if budget_hit:
        context.add_warning(
            "stage_time_budget",
            "verify_results exceeded its time budget; proceeding with partial verification",
        )
    return StepResult(summary={
        "verified": True, "partial": budget_hit,
        # W3.2 A7: verification units are groups (reps + uniques), members
        # inherit; segment count kept for continuity with older summaries.
        "groups": len(verify_targets), "segments": len(identifiers_data),
    })


def _export_results(context):
    """Export system and segment mmCIF files."""
    facade = context.get_value("facade")
    if not facade:
        context.fail("missing_facade", "No facade available for export")

    output_dir = context.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Export whole system
    system_path = output_dir / "system.mmcif"
    try:
        export_system_mmcif(facade, system_path, context.results)
    except Exception as exc:
        logger.warning(f"Whole-system export failed: {exc}")
        context.add_warning("system_export_failed", str(exc))

    # Export each segment
    exported = 1 if system_path.exists() else 0
    for segment in facade.get_segments():
        segment_path = output_dir / f"{segment}.mmcif"
        try:
            export_segment_mmcif(facade, segment, segment_path, context.results)
            exported += 1
        except Exception as exc:
            logger.warning(f"Segment export failed for {segment}: {exc}")
            context.add_warning("segment_export_failed", f"{segment}: {exc}")

    # Record render paths for Mol* Web UI
    if system_path.exists():
        context.results.set_data("render/system_mmcif", str(system_path))
        # Geometry status of the exported system (UI pre-flight / degenerate
        # gate); mirrors ui geometry-check.ts thresholds.
        try:
            from ..loader.scale_guard import geometry_status_from_positions
            context.results.set_data(
                "render/geometry",
                geometry_status_from_positions(facade.universe.atoms.positions),
            )
        except Exception as exc:
            logger.warning(f"geometry status probe failed: {exc}")
    for segment in facade.get_segments():
        segment_path = output_dir / f"{segment}.mmcif"
        if segment_path.exists():
            context.results.set_data(f"render/segments/{segment}/mmcif", str(segment_path))

    return StepResult(
        summary={"exported": True, "files_exported": exported},
        context_updates={"export_directory": str(output_dir)}
    )


def _render_png(context):
    """Render transparent PNG previews (system + segments) from exported mmcifs.

    v3.137 feature: the UI uses these images as static fallbacks whenever the
    interactive Mol* view is unavailable, too slow, or the system is too large
    (>= render reduced-style threshold). This task NEVER fails a run: every
    image failure/skip/timeout becomes a warning, and if export produced no
    mmcifs the task completes with a note. See src_new/render/png_renderer.py.
    """
    from ..render.png_renderer import RenderConfig, plan_renders, render_all, summarize

    facade = context.get_value("facade")
    if not facade:
        # No structure loaded — nothing to render; not an error for the pipeline.
        context.add_warning("render_no_facade", "No facade available; skipping PNG render")
        return StepResult(summary={"rendered": 0, "reason": "no_facade"})

    run_root = Path(context.output_directory)
    cfg = RenderConfig.from_env()
    if not cfg.pymol_bin:
        context.add_warning(
            "render_pymol_unavailable",
            "PyMOL binary not found (BAT3_RENDER_PYMOL_BIN / PATH); skipping PNG render",
        )
        return StepResult(summary={"rendered": 0, "reason": "pymol_unavailable"})

    segments = list(facade.get_segments())
    n_atoms = context.results.get_data("simulation/n_atoms")
    specs = plan_renders(run_root, segments, n_atoms, cfg)
    if not specs:
        context.add_warning(
            "render_no_mmcifs",
            "No exported mmcifs found at run root; skipping PNG render",
        )
        return StepResult(summary={"rendered": 0, "reason": "no_mmcifs"})

    outcomes = render_all(specs, cfg)
    stats = summarize(outcomes)

    # Record paths to results.json under data.render.* (same convention as mmcif)
    for o in outcomes:
        if o.ok:
            if o.is_system:
                context.results.set_data("render/system_png", str(o.png_path))
            else:
                context.results.set_data(f"render/segments/{o.label}/png", str(o.png_path))
            context.add_artifact(o.png_path, description=f"Static PNG render ({o.label})", kind="render")
        elif not o.skipped:
            context.add_warning(
                "render_failed", f"{o.label}: {o.error}",
                {"label": o.label, "error": o.error},
            )

    if stats["skipped"]:
        context.add_warning(
            "render_budget_exhausted",
            f"PNG render total budget exhausted; {stats['skipped']} image(s) skipped",
            {"skipped": stats["skipped"]},
        )

    return StepResult(summary={"png": True, **stats})


def build_load_and_export_tasks():
    """Build the tasks list for the load-and-export pipeline."""
    return [
        Task(
            task_id="discover_input",
            name="Discover Input",
            handler=_discover_input,
        ),
        Task(
            task_id="load_simulation",
            name="Load Simulation",
            handler=_load_simulation,
            requires_tasks=("discover_input",),
        ),
        Task(
            task_id="repair_topology",
            name="Repair Topology",
            handler=_repair_topology,
            requires_tasks=("load_simulation",),
        ),
        Task(
            task_id="unwrap_periodic_boundaries",
            name="Unwrap Periodic Boundaries",
            handler=_unwrap_periodic_boundaries,
            requires_tasks=("repair_topology",),
        ),
        Task(
            task_id="analyze_universe",
            name="Analyze Universe",
            handler=_analyze_universe,
            requires_tasks=("unwrap_periodic_boundaries",),
        ),
        Task(
            task_id="generate_signatures",
            name="Generate Signatures",
            handler=_generate_signatures,
            requires_tasks=("analyze_universe",),
        ),
        Task(
            task_id="identify_molecules",
            name="Identify Molecules",
            handler=_identify_molecules,
            requires_tasks=("generate_signatures",),
        ),
        Task(
            task_id="verify_results",
            name="Verify Results",
            handler=_verify_results,
            requires_tasks=("identify_molecules",),
        ),
        Task(
            task_id="export_results",
            name="Export Results",
            handler=_export_results,
            requires_tasks=("verify_results",),
        ),
        Task(
            task_id="render_png",
            name="Render PNGs",
            handler=_render_png,
            requires_tasks=("export_results",),
        ),
    ]
