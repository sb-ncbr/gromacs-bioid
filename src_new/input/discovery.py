import logging
import re
from pathlib import Path
from .models import InputKind, FileRecord, InputBundle, LoadDecision

logger = logging.getLogger("base")

# c13 S6: resolver query files (tempfile.mkstemp: "tmp" + 8 chars) that a
# killed run left behind in the input directory (resolvers wrote them via
# safe_tmp_dir(working_directory) until S6). The loader's
# _rank_pdb_candidates ranks any non-"average" PDB above MDposit's
# average.pdb, so a stray 23-51-atom ligand query file became the loaded
# system: 8 of the 397 sample entries since c13 (2289, 2623, 2853, 2987,
# 3071, 3089, 3283, 3541); 827 such files sit in 768 corpus input dirs.
_STRAY_TEMP_RE = re.compile(r"^tmp[a-z0-9_]{8}\.(pdb|cif|json)$")


def _is_stray_temp(path: Path) -> bool:
    return bool(_STRAY_TEMP_RE.match(path.name))


# Canonical suffix table (single source of truth; mirrors the mdpc
# loading-strategy pattern). ext -> (file_type, role).
# role:  structure  = carries coordinates + identity (self-sufficient)
#        topology   = engine topology, needs a coordinate source
#        coordinate = positions only (pair with a topology)
#        trajectory = positions over time; used as frame-0 coordinate source
_CANONICAL_SUFFIX_TABLE: dict[str, tuple[str, str]] = {
    # GROMACS
    ".tpr": ("GROMACS_TPR", "structure"),     # topology + coords in one
    ".gro": ("GROMACS_GRO", "coordinate"),
    ".top": ("GROMACS_TOP", "topology"),
    ".itp": ("GROMACS_ITP", "topology"),
    ".trr": ("GROMACS_TRR", "trajectory"),
    # CHARMM / NAMD
    ".psf": ("CHARMM_PSF", "topology"),
    ".crd": ("CHARMM_CRD", "coordinate"),
    ".dcd": ("CHARMM_DCD", "trajectory"),
    # AMBER
    ".prmtop": ("AMBER_PRMTOP", "topology"),
    ".parm7": ("AMBER_PARM7", "topology"),
    ".nc": ("AMBER_NC", "trajectory"),
    ".rst7": ("AMBER_RST7", "coordinate"),
    ".inpcrd": ("AMBER_INPCRD", "coordinate"),
    ".restrt": ("AMBER_RESTRT", "coordinate"),
    ".mdcrd": ("AMBER_MDCRD", "trajectory"),
    # LAMMPS
    ".data": ("LAMMPS_DATA", "structure"),
    # generic
    ".pdb": ("PDB", "structure"),
    # B3 (BH-014 rest): .ent IS PDB-format content (X03) — load as PDB.
    ".ent": ("PDB", "structure"),
    ".cif": ("MMCIF", "structure"),
    # engine-neutral trajectories (.xtc pairs with gromacs OR amber prmtop;
    # the old duplicated dict let AMBER_XTC silently overwrite GROMACS_XTC)
    ".xtc": ("XTC", "trajectory"),
}

_STRUCTURE_TYPES = {t for t, role in _CANONICAL_SUFFIX_TABLE.values() if role == "structure"}


def discover_input_kind(dir_path: Path) -> InputKind | None:
    """Light extension-based input sniff (banner/UIs); the authoritative
    decision is select_best_file_combination.

    A-16 (red-team 3.3): plain delegation to select lost this function's
    light sniff role (a bare .prmtop MUST still read AMBER here — pinned);
    the disagreement cases the audit cited ({parm7, xtc} -> None vs AMBER)
    are fixed in the ladder itself.
    """
    if not dir_path.exists() or not dir_path.is_dir():
        return None

    extensions = set()
    for f in dir_path.iterdir():
        if f.is_file() and not _is_stray_temp(f):
            extensions.add(f.suffix.lower())

    if ".tpr" in extensions:
        return InputKind.GROMACS
    if ".top" in extensions and ".gro" in extensions:
        return InputKind.GROMACS
    if ".itp" in extensions and ".gro" in extensions:
        return InputKind.GROMACS

    if ".prmtop" in extensions:
        return InputKind.AMBER
    _COORD = {".nc", ".rst7", ".inpcrd", ".restrt", ".xtc", ".dcd", ".mdcrd", ".pdb"}
    if ".parm7" in extensions and extensions & _COORD:  # A-16: any coordinate, not only .nc
        return InputKind.AMBER

    if ".psf" in extensions:
        return InputKind.CHARMM

    if ".data" in extensions:
        return InputKind.LAMMPS

    if ".pdb" in extensions:
        return InputKind.PDB
    if ".cif" in extensions or ".mmcif" in extensions:
        return InputKind.MMCIF

    return None


def _looks_like_lammps_data(path: Path, max_lines: int = 64) -> bool:
    """A-16: True when a .data file actually smells like a LAMMPS data file.

    Signature: the header comment usually contains 'LAMMPS', and/or an
    '<n> atoms' section declaration appears in the first lines. Plain text
    energy tables etc. fail both checks.
    """
    import re
    try:
        head = []
        with path.open("r", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                head.append(line)
    except OSError:
        return False
    text = "".join(head)
    if "LAMMPS" in text.split("\n", 1)[0]:
        return True
    return bool(re.search(r"^\s*\d+\s+atoms\b", text, re.MULTILINE))


def inspect_directory(dir_path: Path) -> InputBundle:
    """Inspect directory and create InputBundle with FileRecords."""
    files = []
    counter = 0

    if dir_path.exists() and dir_path.is_dir():
        for f in sorted(dir_path.iterdir()):
            if f.is_file() and _is_stray_temp(f):
                logger.warning(
                    "input discovery: ignoring stray resolver temp file %s "
                    "(left by an interrupted run; c13 S6)", f.name)
                continue
            if f.is_file():
                ext = f.suffix.lower()
                file_type, role = _CANONICAL_SUFFIX_TABLE.get(ext, ("UNKNOWN", "unknown"))
                file_id = f"file_{counter:06d}"
                record = FileRecord.from_path(f, file_id, file_type, role)
                files.append(record)
                counter += 1

    return InputBundle(root_directory=dir_path, files=files)


def select_best_file_combination(bundle: InputBundle) -> LoadDecision:
    """Select the best loading strategy from the bundle."""
    # Build a set of extensions (case-insensitive via name.lower())
    exts = set()
    for f in bundle.files:
        exts.add(f.path.suffix.lower())
    
    # Check files by extension in this priority:
    # 1. .tpr + .gro -> "TPR_GRO", GROMACS (prefer GRO for coordinates)
    if ".tpr" in exts and ".gro" in exts:
        tpr_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".tpr"]
        gro_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".gro"]
        return LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TPR_GRO",
            topology_files=[tpr_files[0]] if tpr_files else [],
        )
    
    # 2. Any .tpr alone -> "TPR_ONLY", GROMACS
    if ".tpr" in exts:
        tpr_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".tpr"]
        return LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TPR_ONLY",
            topology_files=tpr_files[:1],  # Take first tpr
        )
    
    # 3b. A8 (BH-016): .top + .pdb (no .gro) -> "TOP_PDB", GROMACS —
    # topology + structure step instead of degrading to PDB_SINGLE
    if ".top" in exts and ".gro" not in exts and ".pdb" in exts:
        top_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".top"]
        return LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TOP_PDB",
            topology_files=[top_files[0]] if top_files else [],
        )

    # 3c. A8 (BH-016): .itp + .pdb (no .gro/.top) -> "ITP_PDB", GROMACS
    if ".itp" in exts and ".gro" not in exts and ".top" not in exts and ".pdb" in exts:
        itp_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".itp"]
        return LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="ITP_PDB",
            topology_files=[itp_files[0]] if itp_files else [],
        )

    # 3. .top + .gro -> "TOP_GRO", GROMACS
    if ".top" in exts and ".gro" in exts:
        top_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".top"]
        gro_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".gro"]
        return LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TOP_GRO",
            topology_files=[top_files[0]] if top_files else [],
        )
    
    # 4. .itp + .gro -> "ITP_GRO", GROMACS
    if ".itp" in exts and ".gro" in exts:
        itp_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".itp"]
        gro_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".gro"]
        return LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="ITP_GRO",
            topology_files=[itp_files[0]] if itp_files else [],
        )
    
    # 5. .prmtop + .nc or .parm7 + .nc -> "PRMTOP_NC", AMBER
    
    # 5b. .prmtop + .xtc or .parm7 + .xtc -> "PRMTOP_XTC", AMBER
    if (".prmtop" in exts or ".parm7" in exts) and ".xtc" in exts:
        prmtop_files = [f.path for f in bundle.files if f.path.suffix.lower() in (".prmtop", ".parm7")]
        xtc_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".xtc"]
        return LoadDecision(
            input_kind=InputKind.AMBER,
            selected_strategy="PRMTOP_XTC",
            topology_files=[prmtop_files[0]] if prmtop_files else [],
        )
    if (".prmtop" in exts or ".parm7" in exts) and ".nc" in exts:
        prmtop_files = [f.path for f in bundle.files if f.path.suffix.lower() in (".prmtop", ".parm7")]
        nc_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".nc"]
        return LoadDecision(
            input_kind=InputKind.AMBER,
            selected_strategy="PRMTOP_NC",
            topology_files=[prmtop_files[0]] if prmtop_files else [],
        )

    # 5d. A8 (BH-016): .prmtop/.parm7 + .pdb as static structure step
    # (loses to real trajectories above; saves {topology, pdb} deposits
    # from the flat PDB_SINGLE path that lost charges/types)
    if (".prmtop" in exts or ".parm7" in exts) and ".pdb" in exts:
        prmtop_files = [f.path for f in bundle.files
                        if f.path.suffix.lower() in (".prmtop", ".parm7")]
        strat = "PRMTOP_PDB" if ".prmtop" in exts else "PARM7_PDB"
        return LoadDecision(
            input_kind=InputKind.AMBER,
            selected_strategy=strat,
            topology_files=[prmtop_files[0]] if prmtop_files else [],
        )

    # additive: remaining AMBER coordinate sources (ascii traj, then restarts)
    if (".prmtop" in exts or ".parm7" in exts) and ".mdcrd" in exts:
        prmtop_files = [f.path for f in bundle.files if f.path.suffix.lower() in (".prmtop", ".parm7")]
        return LoadDecision(
            input_kind=InputKind.AMBER,
            selected_strategy="PRMTOP_MDCRD",
            topology_files=[prmtop_files[0]] if prmtop_files else [],
        )
    if (".prmtop" in exts or ".parm7" in exts) and (".rst7" in exts or ".inpcrd" in exts or ".restrt" in exts):
        prmtop_files = [f.path for f in bundle.files if f.path.suffix.lower() in (".prmtop", ".parm7")]
        return LoadDecision(
            input_kind=InputKind.AMBER,
            selected_strategy="PRMTOP_RST7",
            topology_files=[prmtop_files[0]] if prmtop_files else [],
        )
    
    # 5b. .data -> LAMMPS (topology + coordinates in one file)
    # A-16 (red-team 3.3): SNIFF the content first — a stray "energies.data"
    # (or any non-LAMMPS table) must not hijack the decision away from a real
    # structure file that is also present.
    if ".data" in exts and any(_looks_like_lammps_data(f.path) for f in bundle.files
                               if f.path.suffix.lower() == ".data"):
        data_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".data"]
        return LoadDecision(
            input_kind=InputKind.LAMMPS,
            selected_strategy="DATA_SINGLE",
            topology_files=data_files[:1],
        )

    # 5c. .psf -> CHARMM. Coordinate source priority: .pdb > .crd > .dcd (frame 0).
    # NOTE: ordered BEFORE the generic .pdb branch — a {psf, pdb} deposit must
    # keep its CHARMM topology instead of degrading to the flat PDB path.
    if ".psf" in exts:
        psf_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".psf"]
        coord_strategy = None
        warnings: list[str] = []
        if ".pdb" in exts:
            coord_strategy = "PSF_PDB"
        elif ".crd" in exts:
            coord_strategy = "PSF_CRD"
        elif ".dcd" in exts:
            coord_strategy = "PSF_DCD"
        else:
            coord_strategy = "PSF_ONLY"
            warnings.append("charmm_psf_without_coordinate_source")
        return LoadDecision(
            input_kind=InputKind.CHARMM,
            selected_strategy=coord_strategy,
            topology_files=[psf_files[0]] if psf_files else [],
            warnings=warnings,
        )

    # 6. .pdb -> "PDB_SINGLE", PDB; .ent carries the same format (B3, X03)
    if ".pdb" in exts or ".ent" in exts:
        pdb_files = [f.path for f in bundle.files
                     if f.path.suffix.lower() in (".pdb", ".ent")]
        return LoadDecision(
            input_kind=InputKind.PDB,
            selected_strategy="PDB_SINGLE",
            topology_files=pdb_files[:1],
            warnings=(["ent_extension_loaded_as_pdb"] if ".ent" in exts
                      and ".pdb" not in exts else []),
        )
    
    # 7. .cif -> "MMCIF_SINGLE", MMCIF
    if ".cif" in exts:
        cif_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".cif"]
        return LoadDecision(
            input_kind=InputKind.MMCIF,
            selected_strategy="MMCIF_SINGLE",
            topology_files=cif_files[:1],
        )
    
    # Fallback: input_kind=None, strategy="UNKNOWN", confidence=0.0, warnings=["No recognized input files found"]
    return LoadDecision(
        input_kind=None,
        selected_strategy="UNKNOWN",
        topology_files=[],
        confidence=0.0,
        warnings=["No recognized input files found"],
    )
