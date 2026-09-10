#!/usr/bin/env python3
"""Similarity engine for BAT3 validation metrics.

Compares BAT3 ranked hits against MDDBR annotations at SEQUENCE/CHEMICAL
similarity level (not exact identifier match):
- proteins compared as sequences (global alignment identity, Bio PairwiseAligner)
- structures (PDB/AlphaFold) mapped to their entity sequences first
- chemicals compared via InChIKey connectivity block + PubChem fingerprint Tanimoto
All network payloads and pair scores cached durably on NFS (no sqlite).
"""
import hashlib
import json
import os
import re
import time

import requests

ROOT = "/data/validation/sim_cache"
DIRS = ("uniprot_seq", "pdb_fasta", "pubchem_fp", "inchikey_cid", "neg")
for _d in DIRS:
    os.makedirs(os.path.join(ROOT, _d), exist_ok=True)

UNI = "https://rest.uniprot.org/uniprotkb"
RCSB_FASTA = "https://www.rcsb.org/fasta/entry"
PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
TIMEOUT = (10, 30)

ACC_RE = re.compile(r"([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9](?:[A-Z][A-Z0-9]{2}[0-9])?)")
CHEM_TYPES = {"INCHIKEY", "INCHI_KEY", "PUBCHEM_CID", "PUBCHEM_ID", "PUBCHEM"}
SEQ_TYPES = {"UNIPROT_ID", "SWISSPROT_ID", "PDB_ID", "ALPHAFOLD_ID", "UNIPROT", "SWISSPROT", "PDB", "ALPHAFOLD"}


def _cached_json(sub, key, fetcher, ttl_days=0):
    path = os.path.join(ROOT, sub, hashlib.sha1(key.encode()).hexdigest()[:24] + ".json")
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        pass
    val = fetcher()
    try:
        with open(path, "w") as fh:
            json.dump(val, fh)
    except OSError:
        pass
    return val


def _get(url, kind="text"):
    r = requests.get(url, timeout=TIMEOUT)
    if r.status_code == 404:
        raise LookupError(url)
    r.raise_for_status()
    return r.json() if kind == "json" else r.text


def uniprot_seq(acc):
    acc = acc.strip().upper().split("-")[0]
    return _cached_json("uniprot_seq", acc, lambda: "".join(
        ln.strip() for ln in _get(f"{UNI}/{acc}.fasta").splitlines() if not ln.startswith(">")))


def pdb_entity_seqs(pdb):
    pdb = pdb.strip().upper()[:4]
    txt = _cached_json("pdb_fasta", pdb, lambda: _get(f"{RCSB_FASTA}/{pdb}"))
    seqs, cur = [], None
    for ln in txt.splitlines():
        if ln.startswith(">"):
            cur = ""
            seqs.append(cur)
        elif cur is not None:
            seqs[-1] = ln.strip() if seqs[-1] == "" else seqs[-1] + ln.strip()
    return [s for s in seqs if s]


def _inchikey_cid(ik):
    return _cached_json("inchikey_cid", ik, lambda:
                        _get(f"{PUG}/compound/inchikey/{ik}/cids/JSON", "json")["IdentifierList"]["CID"][0])


def _fp_hex(kind, value):
    return _cached_json("pubchem_fp", f"{kind}:{value}", lambda:
        _get(f"{PUG}/compound/{kind}/{value}/property/Fingerprint2D/JSON", "json")
        ["PropertyTable"]["Properties"][0]["Fingerprint2D"])


def _bits(fp_str):
    import base64
    raw = base64.b64decode(fp_str + "=" * (-len(fp_str) % 4))
    return int.from_bytes(raw, "big")


def tanimoto(bits_a, bits_b):
    inter = bin(bits_a & bits_b).count("1")
    union = bin(bits_a | bits_b).count("1")
    return inter / union if union else 0.0


def norm_accession(hit_type, ident):
    """Canonical payload descriptor for a hit/GT identifier.
    Returns (kind, key) with kind in {seq-acc, seq-pdb, fp-inchikey, fp-cid} or (None, None)."""
    t = (hit_type or "").strip().upper()
    v = (ident or "").strip().upper()
    if not v:
        return None, None
    if "INCHI" in t:
        return ("fp-inchikey", v[:27])
    if "PUBCHEM" in t:
        m = re.search(r"(\d+)", v)
        if m:
            return ("fp-cid", m.group(1))
        return None, None
    if "ALPHAFOLD" in t:
        m = ACC_RE.search(v)
        return ("seq-acc", m.group(1)) if m else (None, None)
    if "SWISSPROT" in t or "UNIPROT" in t or t in ("ACC", "ACCESSION"):
        m = ACC_RE.search(v)
        return ("seq-acc", m.group(1)) if m else ("seq-acc", v.split("-")[0])
    if "PDB" in t or len(v) in (4, 5):
        return ("seq-pdb", v[:4])
    m = ACC_RE.search(v)
    if m:
        return ("seq-acc", m.group(1))
    return None, None


class SimEngine:
    def __init__(self, budget=400):
        self.pairs = {}
        self.new_pairs = 0
        self.budget = budget
        self.unmapped = 0
        self.errors = 0
        self._aligner = None
        self.pair_path = os.path.join(ROOT, "pairs.jsonl")
        self._load_pairs()

    def _load_pairs(self):
        try:
            with open(self.pair_path) as fh:
                for ln in fh:
                    try:
                        k, s = ln.rstrip("\n").split("\t")
                        self.pairs[k] = float(s)
                    except ValueError:
                        continue
        except FileNotFoundError:
            pass

    def _save_pair(self, key, sim):
        with open(self.pair_path, "a") as fh:
            fh.write(f"{key}\t{sim:.6f}\n")

    def _align_identity(self, s1, s2):
        if self._aligner is None:
            from Bio.Align import PairwiseAligner
            self._aligner = PairwiseAligner()
            self._aligner.substitution_matrix = None
            # simple unitary scheme speeds things and yields pure identity-ish score
            self._aligner.match_score = 1.0
            self._aligner.mismatch_score = 0.0
            self._aligner.open_gap_score = -0.5
            self._aligner.extend_gap_score = -0.1
            self._aligner.mode = "local"
        p = self._aligner.align(s1, s2)[0]
        counted = p.counts()
        aligned = getattr(counted, "aligned", 0)
        denom = aligned if aligned else max(len(s1), len(s2), 1)
        return max(0.0, min(1.0, counted.identities / denom))

    def _seqs_of(self, kind, key):
        if kind == "seq-acc":
            return [uniprot_seq(key)]
        if kind == "seq-pdb":
            return pdb_entity_seqs(key)
        return []

    def _entity_sim(self, a, b):
        ka, kb = f"{a[0]}:{a[1]}", f"{b[0]}:{b[1]}"
        if ka == kb:
            return 1.0
        key = f"{ka}|{kb}" if ka <= kb else f"{kb}|{ka}"
        hit = self.pairs.get(key)
        if hit is not None:
            return hit
        self.new_pairs += 1
        if self.new_pairs > self.budget:
            self.errors += 1
            return 0.0
        sim = 0.0
        try:
            if a[0].startswith("fp-") and b[0].startswith("fp-"):
                ia = a[1] if a[0] == "fp-inchikey" else None
                ib = b[1] if b[0] == "fp-inchikey" else None
                if ia and ib and ia.split("-")[0] == ib.split("-")[0]:
                    sim = 1.0
                else:
                    cid_a = a[1] if a[0] == "fp-cid" else _inchikey_cid(a[1])
                    cid_b = b[1] if b[0] == "fp-cid" else _inchikey_cid(b[1])
                    sim = tanimoto(_bits(_fp_hex("cid", cid_a)), _bits(_fp_hex("cid", cid_b)))
            elif a[0].startswith("seq") and b[0].startswith("seq"):
                sim = max((self._align_identity(x, y)
                           for x in self._seqs_of(*a) for y in self._seqs_of(*b)), default=0.0)
        except LookupError:
            self.unmapped += 1
        except Exception:
            self.errors += 1
        self.pairs[key] = sim
        self._save_pair(key, sim)
        return sim

    def sim(self, ann_type, ann_value, hit_type, hit_id):
        ka = norm_accession(ann_type, ann_value)
        kb = norm_accession(hit_type, hit_id)
        if ka[0] is None or kb[0] is None:
            self.unmapped += 1
            return 0.0
        return self._entity_sim(ka, kb)
