"""Capture the response examples of the public API reference from a live server (2026-11-19).

    python scripts/capture_api_examples.py [--base URL] [--run RUN_ID]

The examples shown in /docs (Swagger) and on the REST API documentation page
are real answers of the BioID server for one example run (by default the
trypsin example, 1c2a4d4b-…, which is kept permanently), trimmed so they stay
readable: long lists keep their first few entries. Only GET calls are made.
Writes src_new/api/openapi_examples.json; src_new/api/openapi_docs.py reads it.
Rerun after a change of the response formats and commit the file.
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

BASE = "https://bioid-ceitec.dyn.cloud.e-infra.cz"
RUN = "1c2a4d4b-94cb-48ec-81a9-d0c0924af8bd"
OUT = Path(__file__).resolve().parent.parent / "src_new" / "api" / "openapi_examples.json"


def get(url: str) -> tuple[str, bytes]:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bioid-capture-examples"}),
                                timeout=120) as r:
        return r.headers.get("Content-Type", ""), r.read()


def first(items: list, n: int) -> list:
    return items[:n]


def per_segment(hits: list, n: int) -> list:
    """The first n hits of each molecule, in the server's order."""
    seen: dict[str, int] = {}
    out = []
    for h in hits:
        seen[h["segment"]] = seen.get(h["segment"], 0) + 1
        if seen[h["segment"]] <= n:
            out.append(h)
    return out


def one_per(items: list, key, n: int) -> list:
    """The first item of each distinct key, at most n items."""
    seen, out = set(), []
    for it in items:
        k = key(it)
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out[:n]


def capture(base: str, run: str) -> dict:
    api = f"{base}/api/v1"

    def j(path: str):
        return json.loads(get(f"{api}{path}")[1])

    def text(path: str, lines: int) -> str:
        body = get(f"{api}{path}")[1].decode()
        return "\n".join(body.splitlines()[:lines]) + "\n"

    ex: dict = {"_source": {"base": base, "run_id": run}}

    status = j(f"/runs/{run}/status")
    status["tasks"] = first(status["tasks"], 3)
    status["warnings"] = one_per(status["warnings"], lambda w: w["code"], 2)
    status["events"] = first(status["events"], 4)
    ex["status"] = status
    ex["summary"] = j(f"/runs/{run}")
    ex["queue"] = j(f"/runs/{run}/queue")
    ex["loading"] = j(f"/runs/{run}/loading")
    ex["render"] = j(f"/runs/{run}/render")
    ex["files"] = j(f"/runs/{run}/files")
    ex["molecules"] = j(f"/runs/{run}/molecules")
    ex["molecule_info"] = j(f"/runs/{run}/molecules/A__v1/info")

    ver = j(f"/runs/{run}/verification")
    ver["hits"] = per_segment(ver["hits"], 2)
    ex["verification"] = ver
    ex["verification_segment"] = {**j(f"/runs/{run}/verification?segment=A__v1")}
    ex["verification_segment"]["hits"] = first(ex["verification_segment"]["hits"], 3)

    ids = j(f"/runs/{run}/identifiers?segment=A")
    ids["hits"] = one_per(ids["hits"], lambda h: h["resolver_name"], 3)
    ids["attempted_resolvers"] = first(ids["attempted_resolvers"], 8)
    ids["failed_resolvers"] = first(ids["failed_resolvers"], 1)
    ex["identifiers"] = ids

    sig = j(f"/runs/{run}/signatures?segment=A__v1")
    sig["signatures"] = [s for s in sig["signatures"]
                         if s["generator"] in ("smiles", "inchi_key", "molecular_formula", "resname")]
    ex["signatures"] = sig

    opts = j("/runs/config/options")
    opts["config"] = {sec: dict(list(vals.items())[:4]) for sec, vals in list(opts["config"].items())[:3]}
    ex["config_options"] = opts

    ex["examples"] = j("/runs/examples?limit=2")
    ex["capabilities"] = j("/capabilities")
    ex["health"] = j("/health")
    ex["results_csv"] = text(f"/runs/{run}/download/results.csv", 20)
    ex["logs"] = text(f"/runs/{run}/logs", 3)
    ex["topology_less_pdb"] = text(f"/runs/{run}/download/topology-less-pdb?segment=A", 5)
    ex["ca_only_pdb"] = text(f"/runs/{run}/download/ca-only-pdb?segment=A", 5)
    results = j(f"/runs/{run}/download/results.json")
    ex["results_json_keys"] = sorted(results)
    return ex


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--base", default=BASE)
    p.add_argument("--run", default=RUN)
    p.add_argument("--out", default=str(OUT))
    a = p.parse_args()
    ex = capture(a.base.rstrip("/"), a.run)
    Path(a.out).write_text(json.dumps(ex, indent=1, ensure_ascii=False) + "\n")
    print(f"{a.out}: {len(ex) - 1} examples")


if __name__ == "__main__":
    main()
