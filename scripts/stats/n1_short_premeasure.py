"""W5 5.5a pre-measure: for the 824 short hitless nucleic sequences, measure how
many have a 100%-pident FULL-LENGTH match in the campaign pdbnt db (and of those,
how many are also both-directional exact: subject_len == query_len).
Read-only; uses blastn-short exactly as the resolver invokes it; sequences come
from n1_nucleic_rows.jsonl sig summaries (payloads <=30nt => full text in head).
"""
import json, subprocess, tempfile, os, collections
from multiprocessing import Pool

ROWS = "/data/validation/n1_nucleic_rows.jsonl"
DB = "/app/databases/pdbnt/pdbnt"
OUT = "/data/validation/n1_short_premeasure.json"

def load_cases():
    cases = []
    for line in open(ROWS):
        r = json.loads(line)
        if r.get("hit"):
            continue
        summ = (r.get("sig_summary") or {}).get("fasta_map_nucleic")
        if not summ:
            continue
        seq = summ.get("head", "")
        n = summ.get("len", 0)
        if seq and n and n == len(seq) and n <= 25:
            cases.append((r["eid"], r["seg"], seq))
    return cases

def probe(case):
    eid, seg, seq = case
    L = len(seq)
    with tempfile.NamedTemporaryFile("w", suffix=".fa", delete=False) as fh:
        fh.write(f">q\n{seq}\n")
        q = fh.name
    try:
        p = subprocess.run(
            ["blastn", "-task", "blastn-short", "-db", DB, "-query", q,
             "-outfmt", "15", "-max_target_seqs", "500", "-num_threads", "1"],
            capture_output=True, timeout=300)
        data = json.loads(p.stdout.decode() or "{}")
        out = {"eid": eid, "seg": seg, "q_len": L, "n_hits": 0,
               "perfect_full": 0, "perfect_both_dir": 0,
               "best_evalue": None, "best_pident": 0.0, "best_cov": 0.0}
        bo = data.get("BlastOutput2")
        if isinstance(bo, list):
            bo = bo[0] if bo else {}
        hits = (bo.get("report", {}).get("results", {}).get("search", {}).get("hits")) or []
        out["n_hits"] = len(hits)
        for hit in hits:
            slen = hit.get("len")
            hsps = hit.get("hsps") or []
            if not hsps:
                continue
            h = hsps[0]
            ident = h.get("identity", 0) / h.get("align_len", 1) if h.get("align_len") else 0
            cov = h.get("align_len", 0) / L if L else 0
            ev = h.get("evalue")
            if ev is not None and (out["best_evalue"] is None or ev < out["best_evalue"]):
                out["best_evalue"] = ev
            out["best_pident"] = max(out["best_pident"], ident)
            out["best_cov"] = max(out["best_cov"], cov)
            if ident == 1.0 and cov == 1.0:
                out["perfect_full"] += 1
                if slen == L:
                    out["perfect_both_dir"] += 1
        return out
    except Exception as e:
        return {"eid": eid, "seg": seg, "q_len": L, "error": str(e)[:120]}
    finally:
        os.unlink(q)

def main():
    cases = load_cases()
    print(f"cases (hitless, fasta<=25nt): {len(cases)}")
    agg = collections.Counter()
    per_len = collections.defaultdict(collections.Counter)
    samples = []
    with Pool(5) as pool:
        for i, res in enumerate(pool.imap_unordered(probe, cases, chunksize=8), 1):
            if "error" in res:
                agg["errors"] += 1
                continue
            L = res["q_len"]
            agg["molecules"] += 1
            per_len[L]["n"] += 1
            if res["perfect_full"]:
                agg["with_perfect_full"] += 1
                per_len[L]["with_perfect_full"] += 1
            if res["perfect_both_dir"]:
                agg["with_perfect_both_dir"] += 1
                per_len[L]["with_perfect_both_dir"] += 1
                if len(samples) < 15:
                    samples.append(res)
            if res["n_hits"] == 0:
                agg["no_blast_rows"] += 1
            if i % 200 == 0:
                print(f"{i}/{len(cases)} perfect_full={agg['with_perfect_full']} both_dir={agg['with_perfect_both_dir']}", flush=True)
    result = {
        "db": DB, "task": "blastn-short", "deadline": None,
        "cases": len(cases),
        "aggregate": dict(agg),
        "per_query_len": {str(k): dict(v) for k, v in sorted(per_len.items())},
        "samples_both_dir": samples,
    }
    json.dump(result, open(OUT, "w"), indent=1)
    print("WROTE", OUT)
    print(json.dumps(result["aggregate"], indent=1))
    print(json.dumps(result["per_query_len"], indent=1))

if __name__ == "__main__":
    main()
