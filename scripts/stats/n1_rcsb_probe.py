import sys, json, traceback
sys.path.insert(0,"/app")
from src_new.config.loader import RunConfig
c=RunConfig.from_ini_path("/data/validation/config_shared.ini")
c.pdb.curr_uuid="validation-4653-20260924075449"

from src_new.identification.resolvers.pdb_struct import PDBStructResolverNucleotide, PDBStructResolverProtein
from src_new.identification.resolvers.mmcif import MmCifResolver
import requests

r=json.loads(open("/data/validation/4653/results.json").read())
gen=r["data"]["signatures"]["SYSTEM"]["generated"]
pdb_payload=gen["topology_less_pdb"]
mmcif_payload=gen["mmcif"]

# 1) direct RCSB request, same shape as resolver builds, with the campaign URL
url="https://bioid.dyn.cloud.e-infra.cz/files/validation-4653-20260924075449/input/input.pdb"
req={"query":{"type":"group","logical_operator":"and","nodes":[
 {"type":"terminal","service":"structure","parameters":{"value":{"url":url,"format":"pdb"},"similarity_type":"local","target_search_space":"assembly","number_of_candidates":10000}},
 {"type":"terminal","service":"text","parameters":{"attribute":"rcsb_entry_info.selected_polymer_entity_types","operator":"in","value":["Nucleic acid (only)"]}}]},
 "return_type":"entry"}
try:
    resp=requests.post("https://search.rcsb.org/rcsbsearch/v2/query", json=req, timeout=60)
    print("DIRECT RCSB:", resp.status_code, resp.text[:400])
except Exception as e:
    print("DIRECT RCSB ERR:", type(e).__name__, str(e)[:300])

# 2) real resolver path (nucleotide mode) on the real payload
open("/tmp/n1_input.pdb","w").write(pdb_payload)
res=PDBStructResolverNucleotide(c)
try:
    out=res._pdb_fetch_similar_structures("/tmp/n1_input.pdb", True)
    print("RESOLVER pdb_struct_nucleotide ->", out[:5], "n=", len(out))
except Exception as e:
    print("RESOLVER EXC:", type(e).__name__, str(e)[:300])
    traceback.print_exc(limit=2)

# 3) mmcif resolver on real mmcif payload
m=MmCifResolver(c)
try:
    out=m._resolve_similarity(mmcif_payload, "/tmp")
    print("RESOLVER mmcif_struct ->", out[:5], "n=", len(out))
except Exception as e:
    print("MMCIF EXC:", type(e).__name__, str(e)[:300])
    traceback.print_exc(limit=2)
