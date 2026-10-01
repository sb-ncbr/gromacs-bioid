# Shared Context Bundle — BioID UI Rework (load before ANY coding)

## Environment facts (verified 2026-10-01)
- Repo root: /home/tomsko/work/bat3 · UI: `ui/` (REWRITE target) · `web/` DEPRECATED (never touch)
- API source: `src_new/api/` (FastAPI) → image `cerit.io/tomsko/bat3-api`, live tag `ui1`
- UI image: `cerit.io/tomsko/bat3-frontend:latest` via `Dockerfile.frontend` → deploy `bat3-ceitec-bat3-web`, ns `ceitec-biodata-ns`
- Live UI: https://bioid-ceitec.dyn.cloud.e-infra.cz · API behind ingress: /runs /files /health /openapi.json → api:8000
- Worker dispatch: celery task `src_new.api.tasks.run_pipeline_task` → queue `validation.ui.celery` (bat3-ui-worker ×2). CONTRACT — do not change.
- Runs data: NFS PVC `bat3-runs-data-ceitec` mounted `/app/runs`; results.json per run; `/files` = static mount.
- Fixtures: `.tmp/tasks/ui-rework/fixtures/<run_id>/{status,molecules,loading,signatures,identifiers,files,render}.json` + verification samples + runs-list.json
- Contract baseline: `.tmp/tasks/ui-rework/contracts/openapi-live-baseline.json` — API responses must remain a SUPERSET.
- Reference runs: a524e039 (pdb, 4 seg), bce4a0fa (gromacs), 787bb198 (POPC lipid), 4964c437 (FAILED)

## Hard rules
1. API: ADDITIVE ONLY. Never modify existing path semantics; new endpoints under `/api/v1` alias mount. After any API edit: regenerate openapi and diff vs baseline (additions only).
2. Do NOT touch: `src_new/pipeline*`, `src_new/results`, worker image, celery wiring, `main.py` (root, different app), validation stack, `web/`, deployment of bat3-ui-worker.
3. Config: pipeline functional config lives in worker `config.ini`; UI only edits run-config JSON posted at submit. Keep existing config keys verbatim.
4. No MUI/emotion in new UI. DS = `@e-infra/design-system@0.1.9` (exact pin) + Tailwind v4 + lucide-react.
5. Audience biologists: plain-language copy, no raw codes/paths/exception text in UI.

## Stack (new ui/)
Vite 6 + React 19 + TS strict · Tailwind CSS v4 (`@import "tailwindcss"; @import "@e-infra/design-system/setup.css"; @source .../dist`) · custom theme primary `#2E7D32` (custom_setup.css mechanism per DS README) · react-router-dom v7 · @tanstack/react-query · openapi-typescript (types gen, script `npm run gen:api`) · react-dropzone · molstar 4.18 (existing integration patterns in legacy `ui/src/Components/MDComponents/MDViewer.tsx`, reuse MVS builder approach) · vitest

## URL / state scheme (deep-linkable — fixes legacy gap)
- `/` frontpage; `/runs/:runId` results; query params `segment` (default SYSTEM) and `tab` (overview|input|signatures|identifiers|verification|warnings); anchor `#warn-<step>` from TaskBar clicks.

## API deltas to implement (additive, under /api/v1 + alias of existing)
- Mount same routers also at `/api/v1` (hello: app.include_router(runs_router, prefix="/api/v1/runs")) — keep legacy paths working.
- POST /runs: also persist `creator_ip` (X-Forwarded-For first hop) into run metadata.
- GET /runs?mine=1 → filter runs by requester IP.
- POST /runs/{run_id}/rerun → requeue with stored input+config (mirror rerun-all logic, single run).
- GET /runs/{run_id}/queue → `{state: queued|running|done, position?, ahead?}` (simple: count pending runs older than this one).
- Fix `database_url` values: PDB strip `_CHAIN` suffix → https://www.rcsb.org/structure/<4ID>; CHEMBL bare id → add CHEMBL prefix; keep schema shape.

## Display mappings (seed — Planner maintains source of truth)
Signature human names: smiles→"SMILES", smiles_not_sanitized→"SMILES (raw)", fasta_map_protein→"Protein FASTA (sequence-mapped)", fasta_resname_protein→"Protein FASTA (residue names)", fasta_map_nucleic→"Nucleic FASTA (sequence-mapped)", fasta_resname_nucleic→"Nucleic FASTA (residue names)", pdb_protein→"PDB structure (protein)", pdb_nucleic→"PDB structure (nucleic)", pdb_backbone_*→"PDB backbone trace (*)", topology_less_pdb→"Quick-search PDB (topology-less)", ca_only_pdb→"Cα-only PDB", mmcif→"mmCIF structure", inchi_key→"InChIKey", molecular_formula→"Molecular formula", morgan_fingerprint→"Morgan fingerprint", selfies→"SELFIES", tdi→"Topological Descriptor Index", lipid_shorthand→"Lipid shorthand", glycan_composition→"Glycan composition", atom→"Atom counts", name_chain/name_molecule/name_segment→"Name (chain/molecule/segment)", fingerprint→"Fingerprint". Unknown key → title-cased fallback.
Groups: Sequence (fasta*), Structure (pdb*, mmcif, topology_less, ca_only), Chemical (smiles*, inchi*, formula, selfies), Fingerprint (morgan, tdi, fingerprint), Name (name_*), Domain (lipid_shorthand, glycan_composition), Basic (atom).
Signature ext: *fasta*→.fasta · smiles→.smi · *pdb*→.pdb · mmcif→.cif · else .txt
Molecule-type icons (lucide, fallback `Shapes`): protein→`Network`(ribbon-like), nucleic→`Dna`, lipid→`Layers`(bilayer), carbohydrate→`Hexagon`(glycan), water/solvent→`Droplet`, ion→`Zap`, small_molecule→`Atom`, other→`Shapes`. Final glyph choice = Coder B w/ user visual pass.
Database base URLs: PDB→https://www.rcsb.org/structure/, UniProt→https://www.uniprot.org/uniprotkb/, AlphaFold→https://alphafold.ebi.ac.uk/entry/, PubChem CID→https://pubchem.ncbi.nlm.nih.gov/compound/, ChEMBL→https://www.ebi.ac.uk/chembl/explore/compound/, ChEBI→https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:, CCD→https://www.wwpdb.org/data/ccd (anchor), AlphaFind→https://alphafind.fi.muni.cz/

## Copy tone rules
- Verified chip: ✓ Verified (green) / ✗ Rejected (red, ⓘ shows rejection_reason).
- Empty results panel when zero hits + failed resolvers present: "Identification could not be completed — some search services were unavailable." (+details in Identifiers tab)
- Never show: file paths, exception types, "file is not a database", resolver names to lay users (Identifiers tab may show resolver names — power users OK, tooltips explain).

## Model routing
Coder tasks tagged [27b] (scaffold, API, nginx, typed client) vs [flash] (components, tabs, ports). Planner (kimi) owns reviews, copy deck, error catalog, openapi diffs.
