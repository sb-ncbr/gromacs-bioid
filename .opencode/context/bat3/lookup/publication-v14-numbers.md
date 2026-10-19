# Publication canonical numbers — v14 (2026-10-07 harvest, drain complete)

## Core Concept
Point-in-time "current truth" plate for every number in the BioID NM paper at v14. For Methods polish + final text sweeps — each number listed with its source artifact. Chronological history lives in `publication-journal.md`; HOW numbers were achieved lives in the relevant handoffs (`failure-mode-audit-handoff.md`, `beyond-gt-measurement-handoff.md`, A4/A5 handoffs).

## Key Points
- **Validation @1/5/10 (S7 v14, 10/10 gates)**: PDB 97.0/98.8/99.5% (n = 11,397) · UniProt 94.0/97.0/98.1% (n = 12,795) · small-mol 94.0/95.8/96.1% (n = 5,993) · ions 96.1% flat presence-scored (n = 1,877) · entry-any 98.6/99.6/99.7%. Audit basis entry-level 98.7% (13,319/13,497 — separate basis, never mix with campaign 98.6%).
- **GT frame**: 32,062 annotations / 13,316 GT-covered / 13,538 scored / 15,185 deposits (2026-10-07 harvest); unresolvable GT×hit pairs = 3,309 (score 0.0, stay in denominator — lower bound). GT counters 9,626/12,541/14,787 (chem/pdb/uniprot signatures).
- **Funnel (Fig. 3, v14 basis)**: 26,368 entities → 26,368 signatured (100%) → 23,669 candidates (89.8%) → 23,246 verified (88.2%); cp-2 refusals 2,699 · cp-3 rejects 423; deposits frame 14,464 with rows / 14,616 strict gate-pass / 15,133 dirs scanned. Nucleic 19.6% = **410**/2,091 (wave-quoted 19.7% = 411 — convention pick pending with author).
- **Fig. 3 bands**: ≤12 nt 123@81.3% · 13–20 nt 1,111@13.1% (designed-oligo valley) · 21–30 nt 95@72.6% · 31–100 nt 243@35.4% · >100 nt 519@1.7%; exact re-scan: 19 exact + 13 near (of 1,527); sequences recovered 94.2%. Per-type scale (means): prot 14.1 sig/932.9 cand/63.4 ver (n = 18,160) · small-mol 11.6/10,338.9/26.0 (5,307) · lipid 11.5/1,739.5/39.7 (799) · nucleic 12.2/51.9/4.9 (2,091) · ions & water 9.9/32.4/6.3 (11); caps: verified ≤100/mol (prot 45.7% at cap).
- **§3.4 beyond-GT (v14, guarded)**: see beyond-gt-measurement-handoff.md. 2,403/14,616 (16.4%); classes 1,354/745/433/83/29/2; Cl unlisted 934/1,378 (68%); metals listed-when-present except 6/510; 531 + 93 + 7,298/6,782/6,629 (+153); refusal 334/15,185.
- **Units bridge (referee-proof)**: Fig. 2's 32,062 molecules → pack ~2/segment into ~17k parents + strand-splitting +9,460 → Fig. 3's 26,368 search segments (granularity merge minus split, nothing lost).
- **Failure taxonomy v14 (final, author-locked)**: loading 334 · download 1 · stale-timeout 9 · timeout 9 · other 425 (of 15,185 queue; 437/708 v13-era framing dropped).

## Details
- Sources: `journal/draft/data/` — campaign_stats_v14.json (metrics, taxonomy, GT counters), fig3_basis_v14.json (funnel/bands, 10/10 reconciliation gates), per_molecule_v2.jsonl (frozen audit frame, 36,159 rows), audit_v2.json, a5-curation-handoff.md (531/93), ghosts_post_mirror.json + ghost_curation.md (6,629/153), s0_casefiles_summary.json (S0-OQ-1 624 rows), beyond_gt_v14{,_rows,_elements}.json(l).
- Figures current: fig1_platform · fig2_validation (v3.3 caption; slot-a image pending author) · fig3_gates (v3.1 SHORT caption) · fig4_beyond (88 mm single-col, caption v1.1; §10/§11 pending-edits). Generators: `journal/draft/figures/gen_fig*.py`; ED tables via `journal/scripts/gen_ed_tables.py` → `journal/tex/ed/` (live).
- Stale nags to burn on next tex pass: §3.3 campaign paragraph still v12-era (14,624 / 14,460 / 26,354→23,658→23,233); Fig. 3 caption v3 "15,134 successfully analyzed deposits" → strict gate-pass 14,616 (filed in pending-edits §11 author action); whole-paper renumber = one dedicated sweep.

# Locality
.opencode/context/bat3/lookup/publication-v14-numbers.md
