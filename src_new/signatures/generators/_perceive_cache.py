"""B-14 (red-team 4.1): perceive-once cache for RDKit chemistry generators.

Historically every RDKit-based generator rebuilt the molecule from the SAME
fragment (atoms -> topology bonds / coordinate perception -> bond-order
determination). The bond-order step (rdDetermineBonds) is the expensive part
(B-01's 106 s NAD case). Generator families with byte-identical build
procedures (smiles-class x2; inchi == selfies) now share one pristine
built Mol per fragment; each generator receives a private Chem.Mol copy for
its own post-processing (RemoveHs/sanitize/encodings), so results are
bit-identical to the uncached path.

Semantics:
- cache key is the AtomGroup itself (MDAnalysis value-hashes by atom
  selection -> one entry per fragment instance even across re-selects);
- build errors are cached too and re-raised to later family members
  (fail-fast; identical error strings recorded per generator, as today);
- BAT3_PERCEIVE_CACHE_OFF=1 bypasses the cache entirely (A/B testing +
  rollback switch);
- timeout_s is a SOFT cap (SIGALRM where preemptible): RDKit C++ calls
  cannot be interrupted mid-flight; the hard subprocess cap is deliberately
  part of the 4.3 (B-07) deadline plumbing.
"""
from __future__ import annotations

import contextvars
import logging
import os
import pickle
import signal
import struct
import subprocess
import sys
import threading
import weakref

from rdkit import Chem

logger = logging.getLogger("base")

_cache: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


class PerceiveTimeoutError(RuntimeError):
    """Perceive build exceeded its soft timeout budget."""


def clear_cache() -> None:
    _cache.clear()


def cache_enabled() -> bool:
    return os.environ.get("BAT3_PERCEIVE_CACHE_OFF", "0") != "1"


def _with_soft_timeout(seconds: float, fn):
    if (seconds and seconds > 0
            and threading.current_thread() is threading.main_thread()
            and hasattr(signal, "SIGALRM")):
        def _handler(signum, frame):
            raise PerceiveTimeoutError(f"perceive build exceeded {seconds}s")
        old = signal.signal(signal.SIGALRM, _handler)
        signal.setitimer(signal.ITIMER_REAL, float(seconds))
        try:
            return fn()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, old)
    return fn()


def build_once_cached(fragment, family: str, builder, timeout_s: float = 0.0):
    """Return a private copy of the fragment's built Mol for `family`.

    The FIRST family member to call pays the build; later members receive
    Chem.Mol copies of the cached pristine Mol, or the same exception again.
    """
    if not cache_enabled():
        return _with_soft_timeout(timeout_s, builder)

    fam = _cache.get(fragment)
    if fam is None:
        fam = _cache[fragment] = {}
    entry = fam.get(family)
    if entry is not None:
        kind, payload = entry
        if kind == "ok":
            return Chem.Mol(payload)
        raise payload
    try:
        mol = _with_soft_timeout(timeout_s, builder)
    except Exception as exc:
        fam[family] = ("err", exc)
        raise
    fam[family] = ("ok", mol)
    return Chem.Mol(mol)


# --- shared family builders -------------------------------------------------

def _atoms_into(fragment, atom_idx_to_index, molecule_build):
    """Atom construction identical to the inchi/selfies family helpers
    (+B-10 H-deficiency correction, h_map=None reproduces it exactly)."""
    from rdkit import Chem as _Chem
    h_map = _h_deficiency(fragment)
    atom_idx_to_rdkit_idx = {}
    for atom_idx in fragment.atoms.indices:
        i = atom_idx_to_index[atom_idx]
        rdkit_atom = _Chem.Atom(str(fragment.atoms.elements[i]).title())
        rdkit_atom.SetNoImplicit(True)
        rdkit_idx = molecule_build.AddAtom(rdkit_atom)
        atom_idx_to_rdkit_idx[atom_idx] = rdkit_idx
        # B-10 counts-mode: inject the mass-inferred implicit H as explicit
        # atoms (open-mode {} and all-atom None: no correction).
        if h_map:
            n = h_map.get(i, 0)
            if n > 0:
                _inject_inferred_hydrogens(molecule_build, rdkit_idx, n)
    return atom_idx_to_rdkit_idx


def _bonds_into(fragment, atom_idx_to_rdkit_idx, molecule_build):
    from rdkit import Chem as _Chem
    for atom_idx1, atom_idx2 in _intra_bond_pairs(fragment):
        molecule_build.AddBond(
            atom_idx_to_rdkit_idx[atom_idx1],
            atom_idx_to_rdkit_idx[atom_idx2],
            _Chem.BondType.SINGLE,
        )


def build_once_family_mol(fragment, skip_bond_orders: bool = False):
    """inchi/selfies family build: atoms + topology bonds + ONE bond-order
    attempt at formal-charge 0 (exception deliberately swallowed, mol keeps
    whatever bond orders were assigned) — byte-identical to both modules'
    historical code.

    W3.1 P24 follow-up: skip_bond_orders=True skips the bond-order
    attempt entirely. Carbohydrate segments (glycans) are carried by the
    glycan_composition signature, and their InChIKey is computed from the
    connectivity (all-single) mol — live evidence (1IGT E/F): the key is
    IDENTICAL whether the ladder times out at 120 s or 300 s, i.e. the
    DBO run contributes nothing while burning the full budget per
    segment."""
    from rdkit import Chem as _Chem
    from rdkit.Chem import rdDetermineBonds as _rdb
    atom_idx_to_index = {
        atom_idx: i for i, atom_idx in enumerate(fragment.atoms.indices)}
    molecule_build = _Chem.EditableMol(_Chem.Mol())
    rdkit_idx = _atoms_into(fragment, atom_idx_to_index, molecule_build)
    _bonds_into(fragment, rdkit_idx, molecule_build)
    # B-08: H-cap attachment points whose bond left the fragment
    els = [str(e).title() for e in fragment.atoms.elements]
    for gidx, n in _external_cut_counts(fragment).items():
        if els[atom_idx_to_index[gidx]] != "H":
            _inject_inferred_hydrogens(molecule_build, rdkit_idx[gidx], n)
    molecule = molecule_build.GetMol()
    if skip_bond_orders:
        logger.info(
            "bond-order determination skipped for this carbohydrate "
            "segment: glycan_composition carries the identity and the "
            "InChIKey is computed from the connectivity mol (1IGT "
            "glycan class — the ladder cannot finish in any budget)")
        return molecule
    try:
        # B-01 (red-team 4.2): topology net charge first, then ladder —
        # replaces the charge=0 single attempt (wrong keys for charged
        # ligands: first-block identical, protonation/charge layer wrong)
        determine_bond_orders_safely(molecule, net_charge=_net_charge(fragment),
                                     fragment=fragment)
    except Exception:
        pass  # historical behavior: unsanitized/all-single is fine here
    return molecule


# --- B-01 (red-team 4.2): charge-aware bond-order determination -------------

_TRIAL_CHARGES = (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6)

# Wave-2 (item 2a): DetermineBondOrders is an exponential valence search in
# RDKit C++ and CANNOT be interrupted by perceive_timeout_s (demonstrated
# wave-1: a 36-residue backbone-only peptide spun >20 min; the d13 75-minute
# signature entry was this same class). Large H-less / coordinate-described
# polymer fragments are exactly the pathological shape for it — skip the
# ladder there (all-single bonds; the sequence/similarity tier carries the
# chemistry), keep it for drug-like sizes where bond-order determination is
# both useful and fast. 60 heavy atoms sits between the two classes (demo
# spin ~46+; typical ligands below).
_BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS = 60


def _is_hless(mol) -> bool:
    return not any(a.GetAtomicNum() == 1 for a in mol.GetAtoms())


def _net_charge(fragment) -> int:
    """Net molecular charge from topology partial charges (prmtop/tpr/psf/
    itp carry them; PDB/GRO typically do not -> 0, unchanged behavior)."""
    try:
        q = float(fragment.atoms.charges.sum())
    except Exception:
        return 0
    return int(round(q))


def _reset_to_single_bonds(mol) -> None:
    """Undo a DetermineBondOrders attempt: historical build state was
    all-SINGLE bonds with zero formal charges (atoms built SetNoImplicit)."""
    from rdkit import Chem as _Chem
    for b in mol.GetBonds():
        b.SetBondType(_Chem.BondType.SINGLE)
    for a in mol.GetAtoms():
        a.SetFormalCharge(0)
        a.SetNoImplicit(True)


def _has_bare_proton_fragment(mol) -> bool:
    """Charge-0 misfit artifact: an isolated [H+] with no bonds (arises when
    RDKit balances a wrong input charge by dumping a bare proton). A correct
    zwitterion (e.g. glycine NH3+/COO-) has its charges bonded in-framework
    and is NOT rejected."""
    for a in mol.GetAtoms():
        if (a.GetAtomicNum() == 1 and a.GetFormalCharge() == 1
                and a.GetDegree() == 0):
            return True
    return False


def determine_bond_orders_safely(mol, net_charge: int = 0,
                                 max_heavy_atoms_hless: int
                                 = _BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS,
                                 fragment=None) -> bool:
    """B-01: try the topology net charge first, then a 0,+-1..+-6 ladder.

    A successful DetermineBondOrders call is ACCEPTED only when the
    solution carries no bare-[H+] fragment artifact (evidence the input
    charge was wrong) and its formal-charge sum matches q. Mol is reset to
    the all-single state between attempts for determinism. Non-ValueError
    failures propagate (smiles semantics); callers that historically
    swallow exceptions keep doing so. Returns True when accepted.

    Wave-2 (item 2a): the charge ladder is SKIPPED for H-less
    fragments above max_heavy_atoms_hless — the uninterruptible
    exponential-spin class; the all-single state is kept for
    similarity-tier chemistry.

    W3 A5 (BH-049): explicit-H multi-carboxylate peptides explode the same
    way (M13: >20 min in the first ladder attempt). Two guards below:
    Fix B runs the carboxylate-capped single-shot DBO first (ms), Fix C
    runs the whole ladder in a killable subprocess with one shared budget
    (BAT3_BOND_ORDER_TIMEOUT_S, default 120 s).

    Wave-2 (item 7): the H-less test must reflect the PRE-INJECTION
    fragment — the B-10 counts-mode injection materialises the inferred
    hydrogens as explicit atoms BEFORE this call, so a mol-side test
    wrongly reports "all-atom" for exactly the class the guard exists for
    (united-atom glycan prompts, 1FC1 110-atom class). Callers pass the
    source fragment; heavy-atom counting is robust because injection only
    ever adds H."""
    n_heavy = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() > 1)
    if fragment is not None:
        try:
            frag_hless = not any(
                str(e).title() == "H" for e in fragment.atoms.elements)
        except Exception:
            frag_hless = _is_hless(mol)
    else:
        frag_hless = _is_hless(mol)
    if (max_heavy_atoms_hless and n_heavy > max_heavy_atoms_hless
            and frag_hless):
        logger.warning(
            "bond-order ladder skipped: %d-heavy-atom H-less fragment > %d "
            "(uninterruptible valence-search class); keeping all-single "
            "bonds for similarity-tier chemistry",
            n_heavy, max_heavy_atoms_hless)
        return False
    # W3 A5 (BH-049) Fix B: carboxylate-capped single-shot DBO BEFORE the
    # ladder. Every odd UA {C,O,O} carboxylate component gets a temporary H
    # on a copy -> every UA component even -> RDKit's first matching is
    # perfect (ms, no enumeration); orders/charges copy back, capped O's
    # restored to -1. Skipped via BAT3_DBO_NO_CAP=1 (tests/rollback).
    if os.environ.get("BAT3_DBO_NO_CAP", "0") != "1":
        # item 3: the capped single-shot runs in the killable worker —
        # never in-process (see _dbo_capped_carboxylate_subprocess).
        status, q_used = _dbo_capped_carboxylate_subprocess(
            mol, net_charge=net_charge)
        if status == "ok":
            logger.debug(
                "bond orders perceived via carboxylate-capped single-shot "
                "at charge %d (BH-049 fast path)", q_used)
            return True
        if status == "timeout":
            return False  # uninterruptible class: the ladder would only
            # burn more budget on the same molecule — continue without
            # bond orders (similarity-tier chemistry, as on every DBO
            # budget miss)
        # "na": not applicable / failed -> historical ladder path
    # W3 A5 (BH-049) Fix C: the whole ladder in a hard-killed subprocess
    # with ONE shared budget. SIGALRM cannot interrupt RDKit C++ (M13 spun
    # >20 min inside DetermineBondOrders); a killable child can.
    return _dbo_ladder_subprocess(mol, net_charge)


def _dbo_ladder_core(mol, net_charge: int) -> bool:
    """The historical B-01 ladder, extracted so it can run inside the
    Fix-C child interpreter (ONE budget shared across all charges)."""
    from rdkit.Chem import rdDetermineBonds as _rdb
    order = [net_charge] + [q for q in _TRIAL_CHARGES if q != net_charge]
    for q in order:
        try:
            _rdb.DetermineBondOrders(
                mol, allowChargedFragments=True, embedChiral=False, charge=q)
        except ValueError:
            _reset_to_single_bonds(mol)
            continue
        no_bare_h = not _has_bare_proton_fragment(mol)
        charge_match = (sum(a.GetFormalCharge() for a in mol.GetAtoms()) == q)
        if no_bare_h and charge_match:
            return True
        # unacceptable solution: reset and continue the ladder
        _has_bare = not no_bare_h
        _reset_to_single_bonds(mol)
        logger.debug(
            "bond-order solution at charge %d rejected (%s)",
            q, "bare [H+] fragment" if _has_bare else "charge mismatch")
    return False


_DBO_CHILD_BOOTSTRAP = """
import sys, os, pickle, struct, importlib.util
# W3.1 item 8 (A5): die with the parent run (PR_SET_PDEATHSIG) — an
# orphaned DBO interpreter kept burning CPU after run termination.
try:
    import ctypes, signal
    ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGKILL)
except Exception:
    pass
spec = importlib.util.spec_from_file_location("dbo_worker", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from rdkit import Chem


def _recv(stream):
    hdr = b""
    while len(hdr) < 4:
        chunk = stream.read(4 - len(hdr))
        if not chunk:
            return None
        hdr += chunk
    (n,) = struct.unpack(">I", hdr)
    buf = b""
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


# W3.1 item 8 (A5): a PERSISTENT worker — one interpreter serves every
# request (was: a fresh ~170 ms interpreter per ligand).
while True:
    payload = _recv(sys.stdin.buffer)
    if payload is None:
        break
    try:
        req = pickle.loads(payload)
        # item 3: 3-tuple requests carry a mode; legacy 2-tuples (stale
        # worker from a pre-fix parent) fall back to the ladder.
        blob, q, mode = (req + ("ladder",))[:3] if len(req) == 2 else req
        mol = Chem.Mol(blob)
        if mode == "capped":
            q_used, out = m._dbo_capped_core(mol, q)
            out = pickle.dumps((True, q_used, out))
        else:
            ok = m._dbo_ladder_core(mol, q)
            out = pickle.dumps((True, bool(ok),
                             mol.ToBinary() if ok else None))
    except Exception as exc:
        out = pickle.dumps((False, str(exc), None))
    sys.stdout.buffer.write(struct.pack(">I", len(out)))
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
"""


def _bond_order_timeout_s() -> float:
    try:
        return float(os.environ.get("BAT3_BOND_ORDER_TIMEOUT_S", "300"))
    except ValueError:
        return 300.0


def _dbo_budget_s(mol) -> float:
    """W3.1 item 8 (A5): the ladder budget — BAT3_BOND_ORDER_TIMEOUT_S
    overrides absolutely; otherwise 300 s base (the 120 s cap starved
    charge-less NAD, which used to succeed in ~210 s) scaled up with
    atom count, hard ceiling 1800 s."""
    override = os.environ.get("BAT3_BOND_ORDER_TIMEOUT_S")
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    try:
        n_atoms = int(mol.GetNumAtoms())
    except Exception:
        n_atoms = 0
    return float(min(max(300, n_atoms), 1800))


# W3.1 P24 follow-up: run-level DBO ladder cap (safety net). The
# generate_signatures stage gets ~240 s of TOTAL ladder time per run:
# 1IGT burns 2 x 300 s on glycans whose identifiers do not depend on
# the outcome (now skipped outright — see build_once_family_mol), and
# any OTHER pathological ladder must not push the stage over the
# structural gate's 300 s wall-time limit either. Charge-less NAD
# (~210 s, single ligand) still fits.
_DBO_RUN_CAP_S_DEFAULT = 240.0
# W3 BH-053: the run-level ladder budget is scoped to the RUN, not the
# process. Under --pool=threads two runs share one interpreter; a single
# module-global accumulator meant run B's stage-start reset erased run
# A's spent budget (A's ladder could then burn 2x the cap) and both
# drained one counter. Keyed by the current run id (set at stage start
# via set_dbo_run_id; the parallel process-pool workers get theirs from
# the config dict).
_dbo_run_elapsed: dict[str, float] = {}
_dbo_run_lock = threading.Lock()
_dbo_run_ctx: "contextvars.ContextVar" = contextvars.ContextVar(
    "dbo_run_id", default=None)


def set_dbo_run_id(run_id) -> None:
    """Scope the run-level DBO ladder budget to THIS run (BH-053).

    Called at generate_signatures stage start (serial path) and in the
    process-pool worker bootstrap; the budget map is keyed by it, so a
    concurrent run's stage-start reset never touches this run's
    remaining budget."""
    _dbo_run_ctx.set(run_id)


def _dbo_run_key() -> str:
    return _dbo_run_ctx.get() or "<default>"


def _dbo_run_cap_s() -> float:
    """BAT3_BOND_ORDER_RUN_CAP_S overrides; default 240 s per run."""
    try:
        return float(os.environ.get(
            "BAT3_BOND_ORDER_RUN_CAP_S", str(_DBO_RUN_CAP_S_DEFAULT)))
    except ValueError:
        return _DBO_RUN_CAP_S_DEFAULT


def dbo_run_budget_reset():
    """Reset THIS run's ladder budget (keyed by run id, BH-053). Called
    at the start of every generate_signatures stage; the process-pool
    workers are spawn-fresh, so their trackers start at zero on their
    own."""
    with _dbo_run_lock:
        _dbo_run_elapsed.pop(_dbo_run_key(), None)


def _dbo_run_remaining_s() -> float:
    with _dbo_run_lock:
        return _dbo_run_cap_s() - _dbo_run_elapsed.get(_dbo_run_key(), 0.0)


class _DboWorkerProcess:
    """W3.1 item 8 (A5): persistent bond-order worker interpreter.

    One child serves every DetermineBondOrders-ladder request for the
    whole process lifetime (a fresh interpreter cost ~170 ms per
    ligand). Runs in its own session (start_new_session) so a timeout
    can kill the whole process GROUP (anything the ladder spawns), and
    sets PR_SET_PDEATHSIG so the worker dies with the parent run — no
    orphaned CPU burn after termination. After a kill the accessor
    respawns on the next request."""

    def __init__(self):
        # own process group: killpg reaches grandchildren too
        self.proc = subprocess.Popen(
            [sys.executable, "-c", _DBO_CHILD_BOOTSTRAP,
             os.path.abspath(__file__)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True)

    def alive(self) -> bool:
        return self.proc.poll() is None

    def kill_group(self):
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        # BH-053: REAP the child — SIGKILL is delivered asynchronously,
        # so an immediate poll() can still report the corpse as alive
        # and the next request would be written into a dead pipe (false
        # bond_order_timeout for one molecule). After wait() the
        # accessor's alive() check is deterministic.
        try:
            self.proc.wait(timeout=5)
        except Exception:
            pass

    def _close(self):
        for stream in (self.proc.stdin, self.proc.stdout):
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass

    def call(self, mol_binary: bytes, net_charge: int,
             budget: float, mode: str = "ladder"):
        """One framed request/response round trip.

        mode: "ladder" (historical charge ladder via _dbo_ladder_core) or
        "capped" (item-3: the carboxylate-capped single-shot via
        _dbo_capped_core — its DetermineBondOrders call is RDKit C++ and
        can spin for hours in-process; the killable child is the only
        protection that works).

        Returns (ran, ok, blob) or None on timeout/death (the caller
        respawns via the accessor on the next request)."""
        payload = pickle.dumps((mol_binary, int(net_charge), str(mode)))
        reply: dict = {}

        def _reader():
            try:
                hdr = self.proc.stdout.read(4)
                if len(hdr) < 4:
                    return
                (n,) = struct.unpack(">I", hdr)
                body = self.proc.stdout.read(n)
                if len(body) < n:
                    return
                reply["value"] = pickle.loads(body)
            except Exception:
                pass

        try:
            self.proc.stdin.write(struct.pack(">I", len(payload)))
            self.proc.stdin.write(payload)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            return None  # worker died: caller respawns
        reader = threading.Thread(target=_reader, daemon=True)
        reader.start()
        reader.join(budget)
        if "value" not in reply:
            self.kill_group()
            return None
        ran, ok, blob = reply["value"]
        if not ran:
            return None
        return (ok, blob)


_dbo_worker_lock = threading.Lock()
# W3 BH-053: ONE worker per calling THREAD (keyed by (pid, thread id)).
# The single process-global worker (W3.1 item 8) was written for the
# serial in-process path; under --pool=threads two runs' concurrent
# ladders interleaved frames on one pipe (a reply could be applied to
# the WRONG molecule — silent wrong bond orders) and one run's timeout
# kill killed the other run's in-flight request (false
# bond_order_timeout). Each thread's worker keeps its own session /
# process group, so a budget kill only ever reaches the requesting
# thread's worker. Keyed by pid as well: a forked child never reuses
# the parent's worker (shared pipes would corrupt the frame protocol).
_dbo_workers: "dict[tuple[int, int], _DboWorkerProcess]" = {}


def _get_dbo_worker():
    """Fork-safe, THREAD-isolated persistent-worker accessor (BH-053).

    One worker interpreter per calling thread: frames never interleave
    and a budget kill only ever hits the requesting thread's own worker
    (each worker runs in its own session/process group). A forked child
    never reuses the parent's worker either (keyed by pid)."""
    key = (os.getpid(), threading.get_ident())
    with _dbo_worker_lock:
        w = _dbo_workers.get(key)
        if w is None or not w.alive():
            if w is not None:
                try:
                    w.kill_group()
                    w._close()
                except Exception:
                    pass
            w = _DboWorkerProcess()
            _dbo_workers[key] = w
        return w


def _reset_dbo_worker():
    """Test hook: drop this process's persistent workers (and their
    interpreters). Workers inherited at fork from a parent pid are left
    alone — they are not ours to kill."""
    with _dbo_worker_lock:
        pid = os.getpid()
        for key in [k for k in _dbo_workers if k[0] == pid]:
            w = _dbo_workers.pop(key)
            try:
                w.kill_group()
                w._close()
            except Exception:
                pass


def _overlay_solved(mol, solved) -> None:
    """Copy perceived bond orders/charges from a solved copy back onto
    mol (shared by the ladder and capped subprocess wrappers)."""
    for b in mol.GetBonds():
        sb = solved.GetBondBetweenAtoms(b.GetBeginAtomIdx(),
                                        b.GetEndAtomIdx())
        b.SetBondType(sb.GetBondType())
    for a in mol.GetAtoms():
        sa = solved.GetAtomWithIdx(a.GetIdx())
        a.SetFormalCharge(sa.GetFormalCharge())
        a.SetNoImplicit(True)


def _dbo_ladder_subprocess(mol, net_charge: int) -> bool:
    """W3.1 item 8 (A5): run the charge ladder in the PERSISTENT worker
    interpreter with a per-request budget (_dbo_budget_s: 300 s base /
    atom-scaled); kill its whole process group and continue without
    bond orders when the budget expires (RDKit C++ is uninterruptible
    in-process; a child is killable). The parent mol is only overlaid
    on success, so a kill leaves the all-single pre-state.

    W3.1 P24 follow-up: the effective budget is capped by the RUN-level
    ladder cap (~240 s total per generate_signatures stage) — a safety
    net so no case can burn 2 x 300 s on ladders whose outcome does
    not change the identifiers."""
    import time as _time
    budget = _dbo_budget_s(mol)
    remaining = _dbo_run_remaining_s()
    if remaining <= 0:
        logger.warning(
            "bond_order_run_budget_exhausted: the run-level DBO ladder "
            "cap (%.1fs, BAT3_BOND_ORDER_RUN_CAP_S) is spent; continuing "
            "without bond orders", _dbo_run_cap_s())
        return False
    budget = min(budget, remaining)
    t0 = _time.monotonic()
    worker = _get_dbo_worker()
    reply = worker.call(mol.ToBinary(), net_charge, budget)
    with _dbo_run_lock:
        key = _dbo_run_key()
        _dbo_run_elapsed[key] = \
            _dbo_run_elapsed.get(key, 0.0) + (_time.monotonic() - t0)
    if reply is None:
        logger.warning(
            "bond_order_timeout: DetermineBondOrders ladder exceeded the "
            "%.1fs budget; worker killed, continuing without bond "
            "orders", budget)
        return False
    accepted, blob = reply
    if not accepted or not blob:
        return False
    solved = Chem.Mol(blob)
    _overlay_solved(mol, solved)
    return True


# --- W3 A5 (BH-049) Fix B: carboxylate-capped single-shot DBO -------------

_COO_STD_VALENCE = {6: 4, 7: 3, 8: 2, 16: 2}


def _ua_odd_carboxylate_os(mol) -> list:
    """One carboxylate O index per ODD unsaturated-atom component holding a
    COO- motif (transplant of logs/final_wo/m13/scripts/m13_fix.py)."""
    ua = set()
    for a in mol.GetAtoms():
        z = a.GetAtomicNum()
        if z in _COO_STD_VALENCE and \
                _COO_STD_VALENCE[z] - a.GetDegree() > 0:
            ua.add(a.GetIdx())
    seen, picks = set(), []
    for s0 in sorted(ua):
        if s0 in seen:
            continue
        comp, st = [], [s0]
        seen.add(s0)
        while st:
            x = st.pop()
            comp.append(x)
            for n in mol.GetAtomWithIdx(x).GetNeighbors():
                y = n.GetIdx()
                if y in ua and y not in seen:
                    seen.add(y)
                    st.append(y)
        if len(comp) % 2 == 0:
            continue
        # cap only the carboxylate motif: a degree-1 O whose carbon carries
        # a second degree-1 O (excludes enolates / nitro / N-oxides)
        for i in sorted(comp):
            at = mol.GetAtomWithIdx(i)
            if at.GetAtomicNum() != 8 or at.GetDegree() != 1:
                continue
            c = at.GetNeighbors()[0]
            if c.GetAtomicNum() != 6:
                continue
            if sum(1 for n in c.GetNeighbors() if n.GetAtomicNum() == 8
                   and n.GetDegree() == 1) == 2:
                picks.append(i)
                break
    return picks


def _derived_charge(mol, picks) -> int:
    """Graph-derived net charge: +1 per 4-connected N, -1 per capped O."""
    npos = sum(1 for a in mol.GetAtoms()
               if a.GetAtomicNum() == 7 and a.GetDegree() == 4)
    return npos - len(picks)


def _dbo_capped_carboxylate(mol, net_charge: int = 0):
    """Protonate one O of every odd UA carboxylate component on a COPY,
    run DBO once at (q + n_capped), copy orders back, restore -1 on the
    capped oxygens. Returns the charge used, or None when not applicable /
    failed -- on failure the mol is left in its all-single pre-state
    (hardened vs the prototype, whose charge-mismatch path mutated mol).
    A non-zero topology net charge wins; otherwise the charge is
    graph-derived."""
    from rdkit.Chem import rdDetermineBonds as _rdb
    from rdkit.Geometry import Point3D
    if _is_hless(mol):
        return None  # capping assumes explicit hydrogens
    picks = _ua_odd_carboxylate_os(mol)
    if not picks:
        return None  # nothing odd -> historical path is already fast
    q = int(net_charge) if net_charge else _derived_charge(mol, picks)
    rw = Chem.RWMol(mol)
    conf = rw.GetConformer() if rw.GetNumConformers() else None
    for oi in picks:
        h = Chem.Atom(1)
        h.SetNoImplicit(True)
        hi = rw.AddAtom(h)
        rw.AddBond(oi, hi, Chem.BondType.SINGLE)
        if conf is not None:
            pt = conf.GetAtomPosition(oi)
            conf.SetAtomPosition(hi, Point3D(pt.x + 0.97, pt.y, pt.z))
    capped = rw.GetMol()
    if capped.GetNumConformers() == 0:
        c = Chem.Conformer(capped.GetNumAtoms())
        capped.AddConformer(c, assignId=True)
    try:
        _rdb.DetermineBondOrders(
            capped, charge=q + len(picks), allowChargedFragments=True,
            embedChiral=False)
    except ValueError:
        return None  # original mol not yet touched
    for b in mol.GetBonds():
        cb = capped.GetBondBetweenAtoms(b.GetBeginAtomIdx(),
                                        b.GetEndAtomIdx())
        b.SetBondType(cb.GetBondType())
    for a in mol.GetAtoms():
        a.SetFormalCharge(capped.GetAtomWithIdx(a.GetIdx()).GetFormalCharge())
        a.SetNoImplicit(True)
    for oi in picks:
        at = mol.GetAtomWithIdx(oi)
        at.SetFormalCharge(at.GetFormalCharge() - 1)
    if sum(a.GetFormalCharge() for a in mol.GetAtoms()) != q:
        _reset_to_single_bonds(mol)  # never hand back a half-rewritten mol
        return None
    return q


def _dbo_capped_core(mol, net_charge: int):
    """Child-interpreter body for the capped single-shot (item 3): run
    the historical _dbo_capped_carboxylate on a PRIVATE copy and return
    (q_used, solved_binary) — or (None, None) when not applicable/failed.
    Never mutates the parent's mol: the parent overlays on success only,
    so a kill leaves the all-single pre-state."""
    work = Chem.Mol(mol)
    q_used = _dbo_capped_carboxylate(work, net_charge)
    if q_used is None:
        return None, None
    return q_used, work.ToBinary()


def _dbo_capped_carboxylate_subprocess(mol, net_charge: int = 0):
    """Item 3 (c13 corpus): the carboxylate-capped single-shot's
    DetermineBondOrders call runs IN THE KILLABLE WORKER, never
    in-process.

    Offline repro (entry 9227, .tmp/redteam/item3_repro): the capped
    attempt itself spun >3 h inside RDKit C++ with no cooperative
    checkpoint — SIGALRM cannot interrupt a C++ call (the W3 A5 hazard
    the ladder's own comment documents; Fix C protected the ladder, Fix B
    never got the same treatment). Fleet evidence: 9227/9260 wall-killed
    at exactly 3 h with ZERO stage-budget warnings.

    Returns ("ok", q_used) when solved+overlaid, ("na", None) when not
    applicable/failed (historical ladder still worth trying), or
    ("timeout", None) when the budget expired (the molecule proved
    uninterruptible-class: the ladder is skipped, we continue without
    bond orders)."""
    import time as _time
    if _is_hless(mol) or not _ua_odd_carboxylate_os(mol):
        return "na", None  # parent-side fast path: no round trip needed
    budget = _dbo_budget_s(mol)
    remaining = _dbo_run_remaining_s()
    if remaining <= 0:
        logger.warning(
            "bond_order_run_budget_exhausted: the run-level DBO cap "
            "(%.1fs, BAT3_BOND_ORDER_RUN_CAP_S) is spent before the "
            "capped single-shot; continuing without bond orders",
            _dbo_run_cap_s())
        return "timeout", None
    budget = min(budget, remaining)
    t0 = _time.monotonic()
    worker = _get_dbo_worker()
    reply = worker.call(mol.ToBinary(), net_charge, budget, mode="capped")
    with _dbo_run_lock:
        key = _dbo_run_key()
        _dbo_run_elapsed[key] = \
            _dbo_run_elapsed.get(key, 0.0) + (_time.monotonic() - t0)
    if reply is None:
        logger.warning(
            "bond_order_timeout: carboxylate-capped single-shot exceeded "
            "the %.1fs budget; worker killed, continuing without bond "
            "orders (ladder skipped: same uninterruptible molecule "
            "class)", budget)
        return "timeout", None
    q_used, blob = reply
    if q_used is None or not blob:
        return "na", None
    solved = Chem.Mol(blob)
    _overlay_solved(mol, solved)
    return "ok", q_used


# --- B-10 (red-team 4.4): united-atom / H-less correction ---------------------

_NOMINAL_MASSES = {
    # keys TITLE-CASE to match the els normalisation below (bughunt
    # BH-022: the table used UPPERCASE keys, so every two-letter element
    # looked up as None and was silently skipped)
    "C": 12.011, "N": 14.007, "O": 15.999, "H": 1.008, "S": 32.06,
    "P": 30.974, "F": 18.998, "Cl": 35.45, "Br": 79.904, "I": 126.904,
    "Se": 78.971, "Na": 22.990, "Mg": 24.305, "K": 39.098, "Ca": 40.078,
    "Fe": 55.845, "Zn": 65.38, "Mn": 54.938, "Cu": 63.546, "B": 10.81,
    "Si": 28.085,
}

# bughunt BH-022: maximum implicit hydrogens a united-atom mass residual may
# encode, per element. A mass residual larger than the element's valence is
# NOT implicit hydrogen — it is a wrong element assignment (CLA->C with
# mass 35.45 computed h=23 -> "CH23"; FE->F in GRO -> "FH37"; NA->N ->
# "H9N"). Elements without a united-atom form (metals, halogens) are never
# H-injected from mass alone.
_MAX_UA_H = {"C": 4, "N": 4, "O": 3, "S": 2, "P": 3, "Si": 4, "B": 4, "Se": 2}
_MASS_RESIDUAL_TOL = 0.15  # |m - nominal - h*1.008| must fit, else not H


def _h_deficiency(fragment):
    """Detect H-deficient (united-atom / H-less) heavy-atom fragments.

    Returns:
      None  -- all-atom system (explicit H present): NO correction, the
               historical SetNoImplicit(True) behavior is untouched;
      {}    -- H-less system whose masses carry no united-atom counts
               (PDB ligands): apply SetNoImplicit(False), RDKit fills
               valences instead of producing radicals/carbanions;
      {pos: n} -- masses-mode (GROMOS/ATB/CHARMM19 UA masses 13/14/15...):
               set exactly n implicit H on fragment atom position pos.
    """
    try:
        els = [str(e).title() for e in fragment.atoms.elements]
    except Exception:
        return None
    if not els or any(e == "H" for e in els):
        return None
    try:
        masses = fragment.atoms.masses
    except Exception:
        return {}
    counts = {}
    for pos, (e, m) in enumerate(zip(els, masses)):
        nominal = _NOMINAL_MASSES.get(e)
        m = float(m) if m else 0.0
        if not nominal or not m:
            continue
        max_h = _MAX_UA_H.get(e)
        if max_h is None:
            # element has no united-atom form (metal, halogen): a mass
            # residual is never implicit hydrogen (bughunt BH-022)
            continue
        h = int(round((m - nominal) / 1.008))
        if not (0 < h <= max_h):
            # beyond the element's valence — wrong element assignment,
            # not a united-atom count (CH23/FH37/H8P/H9N class)
            continue
        if abs(m - nominal - h * 1.008) > _MASS_RESIDUAL_TOL:
            # residual does not decompose into whole hydrogens
            continue
        counts[pos] = h
    if counts:
        return counts
    heavy = [e for e in els if e in _NOMINAL_MASSES and e != "H"]
    return {} if heavy else None


def _inject_inferred_hydrogens(molecule_build, parent_rdkit_idx, count):
    """B-10 counts-mode: united-atom masses name their exact implicit H
    count; materialise those H as explicit atoms so bond-order
    determination sees the true valence budget (UA ethanol -> CCO)."""
    from rdkit import Chem as _Chem
    for _ in range(count):
        h = _Chem.Atom("H")
        h_idx = molecule_build.AddAtom(h)
        molecule_build.AddBond(parent_rdkit_idx, h_idx, _Chem.BondType.SINGLE)


# --- B-11 (red-team 4.5): stereochemistry from 3D ------------------------------

def assign_stereo_from_3d(mol, fragment) -> None:
    """Attach the fragment's 3D coordinates to the built mol and assign
    CIP / E-Z stereochemistry (historical output was always the flat
    UHFFFAOYSA block).

    The atom order follows the family builders exactly: heavy atoms in
    fragment-index order, with B-10 UA-injected hydrogens directly behind
    their parent. Injected H get a deterministic tetrahedral position
    opposite their heavy neighbours. Any failure degrades to the previous
    flat output (stereo is best-effort on top of the 4.1 cache copies).
    """
    import numpy as np
    from rdkit import Chem as _Chem
    try:
        n_heavy = fragment.n_atoms
        if mol.GetNumAtoms() < n_heavy:
            return
        positions = fragment.atoms.positions
    except Exception:
        return
    try:
        h_map = _h_deficiency(fragment) or {}
        atom_idx_to_index = {
            int(a): i for i, a in enumerate(fragment.atoms.indices)}
        order = []
        for atom_idx in fragment.atoms.indices:
            i = atom_idx_to_index[int(atom_idx)]
            parent = len(order)
            order.append(("heavy", np.asarray(positions[i], dtype=float)))
            if h_map:
                for _ in range(h_map.get(i, 0)):
                    order.append(("H", parent))
        if len(order) != mol.GetNumAtoms():
            return
        conf = _Chem.Conformer(len(order))
        for rid, entry in enumerate(order):
            if entry[0] == "heavy":
                conf.SetAtomPosition(rid, tuple(float(x) for x in entry[1]))
        # deterministic tetrahedral H placement (chiral UA centres)
        for rid, entry in enumerate(order):
            if entry[0] != "H":
                continue
            parent = entry[1]
            p = np.asarray(conf.GetAtomPosition(parent), dtype=float)
            v = np.zeros(3)
            cnt = 0
            for bond in mol.GetAtomWithIdx(parent).GetBonds():
                o = bond.GetOtherAtomIdx(parent)
                if o >= len(order) or order[o][0] != "heavy":
                    continue
                q = np.asarray(conf.GetAtomPosition(o), dtype=float)
                d = q - p
                nrm = np.linalg.norm(d)
                if nrm > 1e-9:
                    v += d / nrm
                    cnt += 1
            if cnt and np.linalg.norm(v) > 1e-9:
                conf.SetAtomPosition(rid, tuple(p - v / np.linalg.norm(v) * 1.09))
            else:
                conf.SetAtomPosition(rid, (p[0], p[1], p[2] + 1.09))
        mol.RemoveAllConformers()
        mol.AddConformer(conf, assignId=True)
        # embedChiral=False in DBO strips nothing; assign tags from geometry
        _Chem.AssignStereochemistryFrom3D(mol, replaceExistingTags=True)
    except Exception:
        return


# --- B-08 (red-team 4.7): intra-fragment bonds + H-capping ----------------------

def _intra_bond_pairs(fragment):
    """AtomGroup.bonds returns every bond with >=1 endpoint in the group;
    cross-segment bonds must not reach perception. Returns the list of
    (a1, a2) universe indices with BOTH endpoints inside the fragment."""
    idxset = set(int(a) for a in fragment.atoms.indices)
    out = []
    for a1, a2 in fragment.bonds.indices:
        a1, a2 = int(a1), int(a2)
        if a1 in idxset and a2 in idxset:
            out.append((a1, a2))
    return out


def _external_cut_counts(fragment):
    """B-08: {universe_atom_idx: number of cut external partners} for atoms
    retained in the fragment — used to H-cap attachment points so
    perception sees a chemically valid molecule."""
    idxset = set(int(a) for a in fragment.atoms.indices)
    counts = {}
    for a1, a2 in fragment.bonds.indices:
        a1, a2 = int(a1), int(a2)
        if a1 in idxset and a2 not in idxset:
            counts[a1] = counts.get(a1, 0) + 1
        elif a2 in idxset and a1 not in idxset:
            counts[a2] = counts.get(a2, 0) + 1
    return counts
