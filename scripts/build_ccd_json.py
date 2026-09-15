"""Build databases/ccd.json: curated {resname: InChIKey} from RCSB components.cif.

Curated at build time: placeholders/AA/nucleic/waters/ions excluded, FF aliases
added as extra keys. Full CCD coverage where names are honest.
"""
import gzip, json, os, re, sys, urllib.request

SRC = "https://files.rcsb.org/pub/pdb/data/monomers/components.cif.gz"
DEST = sys.argv[1] if len(sys.argv) > 1 else "databases/ccd.json"

BLACKLIST = {  # mirrored from identification/ccd_client (keep in sync)
    "UNK", "LIG", "MOL", "DRG", "DUM", "XXX", "LGN", "SOL", "MLI",
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    "HID", "HIE", "HIP", "CYX", "ASH", "GLH", "LYN", "MEU",
    "A", "C", "G", "T", "U",
    "DA", "DC", "DG", "DT", "DU",
    # cofactor nucleotides deliberately whitelisted: ATP/ADP/AMP (and G*)
    # are CCD components in the sims and their annotations are common GTs
    "WAT", "HOH", "TP3", "TIP", "TIP3", "OPC", "SPC",
    "NA", "CL", "K", "CA", "MG", "ZN", "MN", "FE", "CU", "NI", "CD", "HG",
    "SO4", "PO4", "EDO", "GOL", "PEG", "ACT",
}
ALIASES = {"CHL1": "CLR", "CHOL": "CLR", "CHL": "CLR", "POP1": "POPC"}

def parse_components(txt: str):
    out = {}
    comp_id = None
    cur = {}
    for line in txt.splitlines():
        if line.startswith("data_"):
            if comp_id and cur.get("ik"):
                ik = cur["ik"].strip()
                if ik and comp_id.upper() not in BLACKLIST:
                    out[comp_id.upper()] = ik
            comp_id = line[5:].strip()
            cur = {}
        elif comp_id and "InChIKey" in line and "pdbx_chem_comp_identifier" in line:
            continue
        elif comp_id and line.strip().startswith("_pdbx_chem_comp_identifier.identifier") or (
            comp_id and cur.get("ik") is None and "InChIKey=" in line):
            pass
    return out

def parse_cif_records(txt: str):
    """Robust per-record parse: capture each record's _chem_comp.id + InChIKey."""
    out = {}
    comp_id = None
    ik = None
    for line in txt.splitlines():
        if line.startswith("data_"):
            if comp_id and ik and comp_id.upper() not in BLACKLIST:
                out[comp_id.upper()] = ik
            comp_id = line[5:].strip()
            ik = None
        elif comp_id and ik is None and "-UHFFFAOYSA-" not in line and '"' in line:
            pass
        elif comp_id and ik is None and "InChIKey" in line:
            for t in line.split():
                v = t.strip('"').strip()
                m = re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", v)
                if m:
                    ik = v
                    break
    if comp_id and ik and comp_id.upper() not in BLACKLIST:
        out[comp_id.upper()] = ik
    return out

def main():
    print("downloading", SRC, file=sys.stderr)
    with urllib.request.urlopen(SRC, timeout=600) as r, gzip.open(r, "rt", errors="ignore") as f:
        txt = f.read()
    print("parsing (%d MB)..." % (len(txt) // (1024 * 1024)), file=sys.stderr)
    out = parse_cif_records(txt)
    for alias, target in ALIASES.items():
        if target in out:
            out[alias] = out[target]
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    with open(DEST, "w") as fh:
        json.dump(out, fh, indent=0, sort_keys=True)
    print(f"wrote {len(out)} entries -> {DEST}")

if __name__ == "__main__":
    main()
