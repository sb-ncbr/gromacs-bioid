from pathlib import Path
from .models import InputKind, FileRecord, InputBundle, LoadDecision


def discover_input_kind(dir_path: Path) -> InputKind | None:
    """Detect input format from files present in directory."""
    # Return None if path doesn't exist or isn't a directory.
    if not dir_path.exists() or not dir_path.is_dir():
        return None
    
    # Collect all file extensions (lowercase)
    extensions = set()
    for f in dir_path.iterdir():
        if f.is_file():
            extensions.add(f.suffix.lower())
    
    # Check for GROMACS (.tpr, or .top + .gro, or .itp + .gro)
    if ".tpr" in extensions:
        return InputKind.GROMACS
    if ".top" in extensions and ".gro" in extensions:
        return InputKind.GROMACS
    if ".itp" in extensions and ".gro" in extensions:
        return InputKind.GROMACS
    
    # Check for AMBER (.prmtop, or .parm7 + .nc)
    if ".prmtop" in extensions:
        return InputKind.AMBER
    if ".parm7" in extensions and ".nc" in extensions:
        return InputKind.AMBER
    
    # Check for PDB (.pdb)
    if ".pdb" in extensions:
        return InputKind.PDB
    
    # Check for MMCIF (.cif)
    if ".cif" in extensions:
        return InputKind.MMCIF
    
    return None


def inspect_directory(dir_path: Path) -> InputBundle:
    """Inspect directory and create InputBundle with FileRecords."""
    # Map extensions to file types:
    ext_to_type = {
        ".pdb": "PDB",
        ".cif": "MMCIF",
        ".top": "GROMACS_TOP",
        ".gro": "GROMACS_GRO",
        ".xtc": "GROMACS_XTC",
        ".tpr": "GROMACS_TPR",
        ".prmtop": "AMBER_PRMTOP",
        ".parm7": "AMBER_PARM7",
        ".nc": "AMBER_NC",
        ".itp": "GROMACS_ITP",
    }
    
    # Role: "structure" for PDB, MMCIF, GROMACS_TPR; otherwise "input"
    structure_types = {"PDB", "MMCIF", "GROMACS_TPR"}
    
    files = []
    counter = 0
    
    if dir_path.exists() and dir_path.is_dir():
        for f in sorted(dir_path.iterdir()):
            if f.is_file():
                ext = f.suffix.lower()
                file_type = ext_to_type.get(ext, "UNKNOWN")
                role = "structure" if file_type in structure_types else "input"
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
    # 1. Any .tpr -> "TPR_ONLY", GROMACS
    if ".tpr" in exts:
        tpr_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".tpr"]
        return LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TPR_ONLY",
            topology_files=tpr_files[:1],  # Take first tpr
        )
    
    # 2. .top + .gro -> "TOP_GRO", GROMACS
    if ".top" in exts and ".gro" in exts:
        top_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".top"]
        gro_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".gro"]
        return LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TOP_GRO",
            topology_files=[top_files[0]] if top_files else [],
        )
    
    # 3. .itp + .gro -> "ITP_GRO", GROMACS
    if ".itp" in exts and ".gro" in exts:
        itp_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".itp"]
        gro_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".gro"]
        return LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="ITP_GRO",
            topology_files=[itp_files[0]] if itp_files else [],
        )
    
    # 4. .prmtop + .nc or .parm7 + .nc -> "PRMTOP_NC", AMBER
    if (".prmtop" in exts or ".parm7" in exts) and ".nc" in exts:
        prmtop_files = [f.path for f in bundle.files if f.path.suffix.lower() in (".prmtop", ".parm7")]
        nc_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".nc"]
        return LoadDecision(
            input_kind=InputKind.AMBER,
            selected_strategy="PRMTOP_NC",
            topology_files=[prmtop_files[0]] if prmtop_files else [],
        )
    
    # 5. .pdb -> "PDB_SINGLE", PDB
    if ".pdb" in exts:
        pdb_files = [f.path for f in bundle.files if f.path.suffix.lower() == ".pdb"]
        return LoadDecision(
            input_kind=InputKind.PDB,
            selected_strategy="PDB_SINGLE",
            topology_files=pdb_files[:1],
        )
    
    # 6. .cif -> "MMCIF_SINGLE", MMCIF
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
