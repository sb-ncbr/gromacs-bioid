import json

BASE = "/home/tomsko/work/bat3/.tmp/tasks/ui-rework/contracts"
live = json.load(open(f"{BASE}/openapi-live-baseline.json"))
src = json.load(open(f"{BASE}/openapi-source-baseline.json"))

def paths(d):
    return set(d.get("paths", {}).keys())

lp, sp = paths(live), paths(src)
print("live_only:", sorted(lp - sp))
print("source_only:", sorted(sp - lp))

div = []
for p in sorted(lp & sp):
    lo, so = live["paths"][p], src["paths"][p]
    if json.dumps(lo, sort_keys=True) != json.dumps(so, sort_keys=True):
        div.append(p)
print("divergent_paths:", div)

ls = set(live.get("components", {}).get("schemas", {}).keys())
ss = set(src.get("components", {}).get("schemas", {}).keys())
print("live_schemas_only:", sorted(ls - ss))
print("source_schemas_only:", sorted(ss - ls))
divs = []
for s in sorted(ls & ss):
    if json.dumps(live["components"]["schemas"][s], sort_keys=True) != json.dumps(
        src["components"]["schemas"][s], sort_keys=True
    ):
        divs.append(s)
print("divergent_schemas:", divs)
