"""Pipeline step definitions for the BAT3 pipeline."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from ..executor.task import Task, StepResult
from ..input.discovery import inspect_directory, select_best_file_combination
from ..loader.strategies import load_simulation
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
        context.fail("load_failed", f"No loading strategy succeeded after {len(result.attempts)} attempts")

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

    facade = LoadedUniverse(
        universe=universe,
        decision=decision,
        repair_report=report,
        results=context.results,
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
    
    # Get all instances from store
    all_instances = store.get_all_instances()
    
    # Create a mapping from segment_name to instance
    segment_to_instance = {}
    for inst in all_instances:
        if inst.segment_ids:
            segment_to_instance[inst.segment_ids[0]] = inst
    
    # Build snapshots for all segments
    snapshots = []
    for segment_name in sorted(facade.get_segments()):
        fragment = facade.get_fragment(segment_name)
        instance = segment_to_instance.get(segment_name)
        
        if instance is None:
            logger.warning(f"No MoleculeInstance found for segment {segment_name}, skipping signatures")
            continue
        
        try:
            snapshot = build_signature_snapshot(segment_name, fragment, instance, facade)
            snapshots.append(snapshot)
        except Exception as e:
            logger.warning(f"Failed to build snapshot for {segment_name}: {e}")
            continue
    
    if not snapshots:
        return StepResult(summary={"generated": True, "segments": 0, "signatures": 0})
    
    # Convert config to dict for workers
    config_dict = context.config.to_dict()
    deadline = budget_deadline(context)
    if deadline is not None:
        config_dict["_stage_deadline_epoch"] = deadline

    # Decide whether to use parallel execution
    use_parallel = (
        context.config.executor.signatures_parallel and
        len(snapshots) > 1
    )

    max_workers = context.config.executor.n_threads

    results = None
    budget_hit = False
    if use_parallel:
        # Run in process pool
        items = [(s.__dict__, config_dict) for s in snapshots]
        results = run_with_process_pool(max_workers, _generate_signatures_worker, items)
    else:
        # Direct serial execution: use real objects, skip snapshot reconstruction
        from ..signatures.registry import get_default_generators
        generators = get_default_generators(context.config.signatures)
        results = []
        _spin_dbg = os.environ.get("SPIN_DEBUG") == "1"
        for segment_name in sorted(facade.get_segments()):
            if _budget_exceeded(context):
                budget_hit = True
                logger.warning(f"generate_signatures: stage time budget exceeded at segment {segment_name}; partial output")
                break
            instance = segment_to_instance.get(segment_name)
            fragment = facade.get_fragment(segment_name)
            if instance is None:
                continue
            generated = {}
            attempted = []
            errors = []
            for generator in generators:
                _g_t0 = time.time()
                try:
                    if generator.is_applicable(instance, fragment, facade):
                        attempted.append(generator.name)
                        if _spin_dbg:
                            print(f"[SPIN] {segment_name}/{generator.name} START", flush=True)
                        sig = generator.generate(instance, fragment, facade)
                        if _spin_dbg:
                            print(f"[SPIN] {segment_name}/{generator.name} DONE {time.time()-_g_t0:.1f}s", flush=True)
                        if sig is not None:
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
            })
    
    # Merge results into context.results in main thread
    generated_count = 0
    for result in results:
        if result is None:
            continue
        
        segment_name = result["segment_name"]
        
        # Record warnings from errors
        for error in result.get("errors", []):
            gen_name = error.get("generator", "unknown")
            error_msg = error.get("error", "unknown error")
            context.add_warning("signature_generator_failed", f"{gen_name}: {error_msg}")
        
        for gen_name, sig in result["generated"].items():
            context.results.set_data(f"signatures/{segment_name}/generated/{gen_name}", sig)
            generated_count += 1
        
        if result.get("attempted"):
            context.results.set_data(f"signatures/{segment_name}/attempted", result["attempted"])
    
    if budget_hit:
        context.add_warning(
            "stage_time_budget",
            "generate_signatures exceeded its time budget; proceeding with partial signatures",
        )
    return StepResult(
        summary={"generated": True, "segments": len(snapshots), "signatures": generated_count,
                 "partial": budget_hit}
    )


def _identify_molecules(context):
    """Identify molecules from generated signatures with optional parallelism."""
    from ..signatures.registry import get_signature_type_map
    from ..executor.parallel import run_with_thread_pool
    from .workers import _identify_molecules_worker
    
    facade = context.get_value("facade")
    if not facade:
        context.fail("missing_facade", "No facade available for identification")
    
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
    
    # Build work items: (fragment_name, valid_sigs, config_dict, sig_type_map) for parallel,
    # or just (fragment_name, valid_sigs) for serial
    items_parallel = []
    items_serial = []
    for fragment_name in sorted(signatures_data.keys()):
        generated = signatures_data[fragment_name].get("generated", {})
        if not generated:
            continue
        
        # Filter out empty signatures
        valid_sigs = {k: v for k, v in generated.items() if v}
        if not valid_sigs:
            continue
        
        items_parallel.append((fragment_name, valid_sigs, context.config.to_dict(), sig_type_map))
        items_serial.append((fragment_name, valid_sigs))
    
    if not items_parallel:
        return StepResult(summary={"identified": True})
    
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
            (fn, vs, {**cfg, "_stage_deadline_epoch": deadline} if isinstance(cfg, dict) else cfg, stm)
            for (fn, vs, cfg, stm) in items_parallel
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

        results = []
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
    for result in results:
        if result is None:
            continue
        
        fragment_name = result["fragment_name"]
        
        # Record warnings from errors
        for error in result.get("errors", []):
            resolver_name = error.get("resolver", "unknown")
            gen_name = error.get("generator", "unknown")
            error_msg = error.get("error", "unknown error")
            context.add_warning("identifier_resolver_failed", f"{resolver_name} ({gen_name}): {error_msg}")
        
        for path, value in result["results"].items():
            context.results.set_data(path, value)
    
    if budget_hit:
        context.add_warning(
            "stage_time_budget",
            "identify_molecules exceeded its time budget; proceeding with partial identifications",
        )
    return StepResult(
        summary={"identified": True, "partial": budget_hit}
    )


def _verify_results(context):
    """Verify identification results with optional parallelism."""
    from ..executor.parallel import run_with_thread_pool
    from .workers import _verify_results_worker
    
    facade = context.get_value("facade")
    if not facade:
        context.fail("missing_facade", "No facade available for verification")
    
    # Get all segments from identifiers data
    identifiers_data = context.results.get_data("identifiers")
    if not identifiers_data or not isinstance(identifiers_data, dict):
        return StepResult(summary={"verified": True})
    
    # Read signatures data once
    signatures_data = context.results.get_data('signatures') or {}
    
    # Build work items: (segment, segment_identifiers_data, config_dict, segment_signatures_data)
    deadline = budget_deadline(context)
    items = []
    for segment in sorted(identifiers_data.keys()):
        segment_data = identifiers_data[segment]
        cfg = context.config.to_dict()
        if deadline is not None:
            cfg["_stage_deadline_epoch"] = deadline
        items.append((segment, segment_data, cfg, signatures_data.get(segment)))

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
    for result in results:
        if result is None:
            continue
        
        segment = result["segment"]
        verified_hits = result["verified_hits"]
        
        # Record warnings from errors
        for error in result.get("errors", []):
            error_msg = error.get("error", "unknown error")
            context.add_warning("verification_failed", f"{segment}: {error_msg}")
        
        context.results.set_data(f"verification/{segment}/verified_hits", verified_hits)

    if budget_hit:
        context.add_warning(
            "stage_time_budget",
            "verify_results exceeded its time budget; proceeding with partial verification",
        )
    return StepResult(summary={"verified": True, "partial": budget_hit})


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
    for segment in facade.get_segments():
        segment_path = output_dir / f"{segment}.mmcif"
        if segment_path.exists():
            context.results.set_data(f"render/segments/{segment}/mmcif", str(segment_path))

    return StepResult(
        summary={"exported": True, "files_exported": exported},
        context_updates={"export_directory": str(output_dir)}
    )


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
    ]
