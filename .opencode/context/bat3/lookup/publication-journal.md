# Publication Journal Workspace (Nature Methods submission)

## Core Concept
`journal/` is the isolated research+manuscript workspace for the BioID Nature Methods paper. No code/deployment artifacts. **Canonical manuscript = Overleaf (since 2026-10-05)**; local `journal/tex/main.tex` is a frozen pre-Overleaf snapshot (15-page PDF) — do NOT edit local tex.

## Key Points
- **Workflow (post-Overleaf)**: step by step through `draft/open-items.md`; assistant supplies paste-ready LaTeX snippets, author applies them in Overleaf; figures still regenerated locally (`gen_fig*.py`), author uploads outputs to Overleaf `figures/`
- **Local snapshot**: `journal/tex/main.tex` + `bioid.bib` (23 verified refs), historical build: `pdflatex main && bibtex main && pdflatex main ×2` in `journal/tex/`
- **Drafts/analysis (markdown mirror + evidence)**: `journal/draft/` — `method-inventory.md`, `freetalk-distilled.md`, `manuscript.md` (v0.2 mirror), `cover-letter.md`, `open-items.md` (TODO tracker), `data/` (v11/v12 stats packages + funnel + n1 nucleic audits)
- **Figures** (`journal/draft/figures/`): gen_fig{1,2,3}.py → fig1_platform / fig2_validation / fig3_gates (183mm, PDF/PNG/SVG); regenerate `python3 gen_figN.py`; copied into `journal/tex/figures/`
- **ED tables**: `journal/scripts/gen_ed_tables.py` reads `draft/data/*.json` → `journal/tex/ed/ed_table_{1,2}.{tex,csv}` (never hand-edit)
- **Research corpus**: `journal/blueprint/` (BLUEPRINT + patterns + phrasebank + checklist), `journal/articles/` (20 NM paper analyses), `journal/guidelines/` (NM rules digest), `journal/corpus/` (metrics/fulltexts), `journal/Gromacs_extractor/` (style template donor)
- **Resume file**: `journal/SESSION-RESUME.md` (post-compaction pickup)

## Frozen campaign numbers (S7 v12, 2026-10-04) — quote these
- GT eval frame: 14,624 deposits campaign · 13,324 live-scored · 13,103 GT-covered
- GT annotations: 31,356 = 12,575 UniProt + 11,186 PDB + 5,784 InChIKey + 1,811 ions
- Hit@10 verified: PDB 99.5% · UniProt 98.2% · small-mol 92.9% · ion 95.9% · entry-any 99.5%
- Molecule funnel (13,916 analyzed deposits): 25,842 entities → 25,842 signatured (Gate1 0 refusals) → 23,161 candidates (Gate2 −10.4%) → 22,707 verified (Gate3 −1.8%; per-class: prot 93.6%, other 94.6%, nucleic 19.6%)
- Nucleic wave: 1.89%→19.75%; ≤30-nt oligos 93.3% absent from reference DBs (e-value physics: ≤30nt queries can't pass E≤0.1 even as self-hits); W5 exact-identity ≤25nt lane
- Evolution v8→v12: ion 35.1→95.9, inchikey 90.6→92.9 @10

## Open items (author input pending)
Throughput/entry · use-case deposit for Fig. 5 · beyond-GT counts · author contributions/funding · URL/license/DOIs · Fig. 6 screenshots · title choice (A/B/C) · competing-interests confirm

## Reference
- `journal/README.md` — full workspace index
- `draft/open-items.md` — live TODO tracker
