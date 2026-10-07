#!/usr/bin/env python3
"""Similarity engine for BAT3 validation metrics.

Compares BAT3 ranked hits against MDDBR annotations at SEQUENCE/CHEMICAL
similarity level (not exact identifier match):
- proteins compared as sequences (global alignment identity, Bio PairwiseAligner)
- structures (PDB/AlphaFold) mapped to their entity sequences first
- chemicals compared via InChIKey connectivity block + PubChem fingerprint Tanimoto

Chemistry now scores in SKELETON-FP space (H-scrub collapsed Morgan r2/2048,
same currency as the F7 verification gate): entity kinds are versioned
skel-cid/skel-inchikey so legacy CACTVS pairs never collide.
All network payloads and pair scores cached durably on NFS (no sqlite).
"""
import hashlib
import json
import os
import re
import time

import requests

import sys
for _p in ("/app", os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "."):
    if os.path.isdir(os.path.join(_p, "src_new")) and _p not in sys.path:
        sys.path.insert(0, _p)
from src_new.signatures.skeletize import (
    from_smiles as _sk_from_smiles,
    skeleton_fp as _sk_fp,
    tanimoto as _sk_tanimoto,
)

ROOT = os.environ.get("SIM_CACHE_ROOT", "/data/validation/sim_cache")
DIRS = ("uniprot_seq", "pdb_fasta", "pubchem_fp", "pubchem_smiles", "inchikey_cid", "inchikey_smiles", "neg")
try:
    for _d in DIRS:
        os.makedirs(os.path.join(ROOT, _d), exist_ok=True)
except OSError:
    pass  # read-only/offline environments: fall through to direct fetch

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
        os.makedirs(os.path.dirname(path), exist_ok=True)
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


_CHEMSPIDER_KEY = os.environ.get("CHEMSPIDER_API_KEY", "MoJ1UDD4JE1I5QEb4wLEF1ZiNVrWiSl717c8ue7q")


def _inchikey_chemspider(ik):
    """InChIKey -> SMILES via ChemSpider (key-depleting; use AFTER cactus/pug)."""
    try:
        f = requests.post(
            "https://api.rsc.org/compounds/v1/filter/inchikey",
            headers={"apikey": _CHEMSPIDER_KEY, "Content-Type": "application/json"},
            json={"inchikey": ik}, timeout=30,
        )
        if f.status_code != 200:
            raise LookupError(f"chemspider filter {f.status_code}")
        qid = f.json().get("queryId")
        for _ in range(10):
            time.sleep(1.5)
            st = requests.get(f"https://api.rsc.org/compounds/v1/filter/{qid}/status",
                              headers={"apikey": _CHEMSPIDER_KEY}, timeout=20)
            if st.status_code == 200 and st.json().get("status") == "Complete":
                break
        res = requests.get(f"https://api.rsc.org/compounds/v1/filter/{qid}/results",
                           headers={"apikey": _CHEMSPIDER_KEY}, timeout=20)
        rr = res.json().get("results") or []
        if not rr:
            raise LookupError("chemspider no results")
        det = requests.get(
            f"https://api.rsc.org/compounds/v1/records/{rr[0]}/details?fields=smiles",
            headers={"apikey": _CHEMSPIDER_KEY}, timeout=20)
        smi = (det.json() or {}).get("smiles")
        if smi:
            return smi
        raise LookupError("chemspider empty smiles")
    except requests.RequestException as exc:
        raise LookupError(str(exc))


def _inchikey_idsm(ik):
    """InChIKey -> SMILES via IDSM SPARQL descriptor search (PUG-independent)."""
    q = ('SELECT ?c WHERE { ?c <http://semanticscience.org/resource/SIO_000008> ?d . '
         '?d a ?t . FILTER(CONTAINS(STR(?t), "InChIKey")) '
         '?d <http://semanticscience.org/resource/SIO_000300> ?v . '
         f'FILTER(?v = "{ik}") }} LIMIT 2')
    try:
        d = _get(
            "https://idsm.elixir-czech.cz/sparql/endpoint/idsm?query="
            + requests.utils.quote(q) + "&format=application/sparql-results%2Bjson", "json")
        b = d.get("results", {}).get("bindings", [])
        if not b:
            raise LookupError("idsm ik unknown")
        cu = b[0]["c"]["value"]
        q2 = (f'SELECT ?v WHERE {{ <{cu}> <http://semanticscience.org/resource/SIO_000008> ?d . '
              '?d a ?t . FILTER(CONTAINS(STR(?t), "SMILES")) '
              '?d <http://semanticscience.org/resource/SIO_000300> ?v } LIMIT 2')
        d2 = _get(
            "https://idsm.elixir-czech.cz/sparql/endpoint/idsm?query="
            + requests.utils.quote(q2) + "&format=application/sparql-results%2Bjson", "json")
        b2 = d2.get("results", {}).get("bindings", [])
        if b2:
            v = (b2[0].get("v") or {}).get("value")
            if v:
                return v.strip()
    except LookupError:
        raise
    raise LookupError("idsm ik unresolved")


def _inchikey_smiles(ik):
    """InChIKey -> SMILES. Chain (chembl-inchikey removed: it returns
    cross-contaminated/wrong structures): cactus -> pug -> ChemSpider -> IDSM.

    WATCH: ChemSpider is token-limited; order keeps it late.
    """
    def _fetch():
        # 1) cactus (cheap + broad); charged-species keys (-Q/-S/... ) try the
        # neutral -N form too: public registers only index neutral keys.
        cactus_variants = [ik] if ik.endswith("-N") else [ik, ik[:-1] + "N"]
        for cik in cactus_variants:
            try:
                smi = _get(f"https://cactus.nci.nih.gov/chemical/structure/{cik}/smiles").strip()
                if smi and " " not in smi and "<" not in smi:
                    return smi
            except Exception:
                continue
        # 2) pug (cluster IP may be blocked; neutral -N variant on top)
        for pik in cactus_variants:
            try:
                smi = _get(f"{PUG}/compound/inchikey/{pik}/property/CanonicalSMILES/TXT", "text").strip()
                if smi and " " not in smi:
                    return smi
            except Exception:
                continue
        # 3) chemspider (token-budgeted)
        try:
            return _inchikey_chemspider(ik)
        except LookupError:
            pass
        # 4) idsm inchikey descriptor
        return _inchikey_idsm(ik)
    return _cached_json("inchikey_smiles", ik, _fetch)


def _fp_hex(kind, value):
    return _cached_json("pubchem_fp", f"{kind}:{value}", lambda:
        _get(f"{PUG}/compound/{kind}/{value}/property/Fingerprint2D/JSON", "json")
        ["PropertyTable"]["Properties"][0]["Fingerprint2D"])


def _cid_smiles_idsm(cid):
    """CID -> SMILES via IDSM SPARQL (ELIXIR-CZ PubChem mirror, PUG-independent)."""
    q = (
        "SELECT ?v WHERE { "
        f"<http://rdf.ncbi.nlm.nih.gov/pubchem/compound/CID{cid}> "
        "<http://semanticscience.org/resource/SIO_000008> ?d . "
        "?d a ?t . "
        'FILTER(CONTAINS(STR(?t), "SMILES")) '
        "?d <http://semanticscience.org/resource/SIO_000300> ?v "
        "} LIMIT 2"
    )
    url = ("https://idsm.elixir-czech.cz/sparql/endpoint/idsm?query="
           + requests.utils.quote(q) + "&format=application/sparql-results%2Bjson")
    try:
        d = _get(url, "json")
        for b in d.get("results", {}).get("bindings", []):
            v = (b.get("v") or {}).get("value")
            if v:
                return v.strip()
    except LookupError:
        pass
    raise LookupError(f"idsm cid unresolved: {cid}")


def _cid_smiles(cid):
    """Canonical structure for a CID (PUG first, IDSM mirror fallback)."""
    def _fetch():
        try:
            d = _get(f"{PUG}/compound/cid/{cid}/property/ConnectivitySMILES,SMILES/JSON", "json")
        except LookupError:
            try:
                d = _get(f"{PUG}/compound/cid/{cid}/property/CanonicalSMILES/JSON", "json")
            except LookupError:
                return _cid_smiles_idsm(cid)
        p0 = d["PropertyTable"]["Properties"][0]
        return p0.get("ConnectivitySMILES") or p0.get("SMILES") or p0.get("CanonicalSMILES")
    return _cached_json("pubchem_smiles", f"cid:{cid}", _fetch)


def _skel_tanimoto_cids(cid_a, cid_b):
    fa = _sk_fp(_sk_from_smiles(_cid_smiles(cid_a)))
    fb = _sk_fp(_sk_from_smiles(_cid_smiles(cid_b)))
    return _sk_tanimoto(fa, fb)


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
        return ("skel-inchikey", v[:27])
    if "PUBCHEM" in t:
        m = re.search(r"(\d+)", v)
        if m:
            return ("skel-cid", m.group(1))
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
        self._attempted = set()
        self._negmemo = {}
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
        neg = self._negmemo.get(key)
        if neg is not None:
            return neg  # A1.1: this engine run already failed this pair;
            # same-run recurrences return the transient zero WITHOUT re-running
            # the resolver chain (v14 stall evidence 2026-10-07: single-thread
            # sim loop re-chained 6.8k ghost pairs per occurrence). Memory only
            # -- never written to self.pairs or disk; fresh instances retry.
        # A1/F-7: budget counts distinct first-attempts only (recurrences of a
        # failed pair must not re-burn budget -- a few hot ligands would drain
        # it on an outage day and the rest of the run would soft-zero).
        # The budget block and the failure branches below return WITHOUT
        # touching the pair cache: a failed lookup must never become an
        # immortal cached zero (F-7 poisoning); it retries on the next call.
        if key not in self._attempted:
            self._attempted.add(key)
            self.new_pairs += 1
        if self.new_pairs > self.budget:
            self.errors += 1
            return 0.0
        sim = 0.0
        try:
            if a[0].startswith("skel-") and b[0].startswith("skel-"):
                ia = a[1] if a[0] == "skel-inchikey" else None
                ib = b[1] if b[0] == "skel-inchikey" else None
                if ia and ib and ia.split("-")[0] == ib.split("-")[0]:
                    sim = 1.0
                else:
                    smi_a = _inchikey_smiles(a[1]) if ia else _cid_smiles(a[1])
                    smi_b = _inchikey_smiles(b[1]) if ib else _cid_smiles(b[1])
                    sim = _sk_tanimoto(
                        _sk_fp(_sk_from_smiles(smi_a)),
                        _sk_fp(_sk_from_smiles(smi_b)),
                    )
            elif a[0].startswith("seq") and b[0].startswith("seq"):
                sim = max((self._align_identity(x, y)
                           for x in self._seqs_of(*a) for y in self._seqs_of(*b)), default=0.0)
        except LookupError:
            self.unmapped += 1
            self._negmemo[key] = 0.0  # in-run negative memo; NOT persisted (A1)
            return 0.0  # transient for this run; fresh instances retry
        except Exception:
            self.errors += 1
            self._negmemo[key] = 0.0
            return 0.0  # transient for this run; fresh instances retry
        # Reached only on successful resolution -- genuinely computed zeros
        # included, which DO cache (rerun cost control).
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
