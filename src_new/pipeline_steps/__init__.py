"""Pipeline step definitions for the BAT3 pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

from ..executor.task import Task, StepResult
from ..input.discovery import inspect_directory, select_best_file_combination
from ..loader.strategies import load_simulation
from ..loader.repair import TopologyRepair
from ..loader.universe_facade import LoadedUniverse
from ..loader.fragment_store import FragmentStore
from ..loader.export_mmcif import export_system_mmcif, export_segment_mmcif
from ..verification.manager import VerificationManager

logger = logging.getLogger("base")


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

    context.record_data("repair/report", report.to_dict())
    return StepResult(
        summary={"repaired": True, **report.to_dict()},
        context_updates={"repair_report": report}
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
    """Generate signatures for all segments."""
    from ..signatures.registry import get_default_generators
    
    facade = context.get_value("facade")
    store = context.get_value("fragment_store")
    
    if not facade or not store:
        context.fail("missing_facade", "No facade available for signature generation")
    
    # Build the registry with config
    generators = get_default_generators(context.config.signatures)
    
    # Get all instances from store
    all_instances = store.get_all_instances()
    
    # Create a mapping from segment_name to instance
    segment_to_instance = {}
    for inst in all_instances:
        if inst.segment_ids:
            segment_to_instance[inst.segment_ids[0]] = inst
    
    generated_count = 0
    
    for segment_name in sorted(facade.get_segments()):
        fragment = facade.get_fragment(segment_name)
        instance = segment_to_instance.get(segment_name)
        
        if instance is None:
            logger.warning(f"No MoleculeInstance found for segment {segment_name}, skipping signatures")
            continue
        
        attempted_generators = []
        
        for generator in generators:
            if generator.is_applicable(instance, fragment, facade):
                attempted_generators.append(generator.name)
                sig = generator.generate(instance, fragment, facade)
                if sig is not None:
                    context.results.set_data(f"signatures/{segment_name}/generated/{generator.name}", sig)
                    generated_count += 1
        
        # Record which generators were attempted
        if attempted_generators:
            context.results.set_data(f"signatures/{segment_name}/attempted", attempted_generators)
    
    return StepResult(
        summary={"generated": True, "segments": len(facade.get_segments()), "signatures": generated_count}
    )


def _identify_molecules(context):
    """Identify molecules from generated signatures."""
    from ..identification.registry import get_default_resolvers, IdentifierRegistry
    from ..identification.resolution_manager import IdentifierResolutionManager
    from ..signatures.registry import get_signature_type_map
    
    facade = context.get_value("facade")
    if not facade:
        context.fail("missing_facade", "No facade available for identification")
    
    # Build registry and manager
    resolvers = get_default_resolvers(context.config)
    registry = IdentifierRegistry(resolvers)
    
    sig_type_map = get_signature_type_map(context.config.signatures)
    manager = IdentifierResolutionManager(
        registry, context.config, signature_type_map=sig_type_map
    )
    
    # Run resolution
    manager.resolve_all(context.results, working_directory=str(context.working_directory))
    
    return StepResult(
        summary={"identified": True}
    )




def _verify_results(context):
    """Verify identification results using canonical signatures."""
    from ..verification.manager import VerificationManager
    
    facade = context.get_value("facade")
    if not facade:
        context.fail("missing_facade", "No facade available for verification")
    
    # Create VerificationManager and run verification
    manager = VerificationManager(context.config)
    manager.verify_all(context.results)
    
    return StepResult(summary={"verified": True})


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
    """Build the task list for the load-and-export pipeline."""
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
            task_id="analyze_universe",
            name="Analyze Universe",
            handler=_analyze_universe,
            requires_tasks=("repair_topology",),
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
