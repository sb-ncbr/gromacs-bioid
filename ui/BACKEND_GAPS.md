# Backend gaps for the BioID run-results redesign

**Date:** 2026-10-26
**Author:** UI fork (redesign of `/runs/:id`)
**For:** backend fork / API owner
**Spec:** `bioid_ui_handoff/DATA.md` §4 (IDs G1–G9 kept) — this document is the actionable version, with exact endpoints and current code references.

The redesigned page is built to ship **with the documented fallbacks** and to flip each enhancement on as the corresponding backend change lands. Nothing below blocks the UI work; the priority column says what hurts most to live without.

---

## Priority order (UI perspective)

| Prio | ID | One-liner |
|---|---|---|
| 1 | G5 | Hit names (`name`, `organism`) on verified hits |
| 2 | G4 | `segment` + `service` in warning `details` |
| 3 | G3 | Copies per segment + clean display name |
| 4 | G2 | Per-segment progress during identification |
| 5 | G1 | `run_name` in run summary |
| 6 | G6 | Run-level CSV download |
| 7 | G9 | Per-molecule selector for the system mmCIF |
| 8 | G8 | Typical duration per system class |
| — | G7 | `unique_molecules` key collision (not used by the design; investigate independently) |

---

## G1 — `run_name` missing from run summary

- **Endpoint:** `GET /api/v1/runs/{id}` (`RunSummaryResponse`, `src_new/api/models.py:299`)
- **Request:** add `run_name: str | None` (whatever the user supplied at submission; `null` for unnamed runs).
- **Consumed as:** page title, browser tab title, run list.
- **UI fallback (shipping):** first input file name from `GET /{id}/files`.
- **Effort:** small (field passthrough).

## G2 — No per-segment progress during identification

- **Endpoint:** `GET /api/v1/runs/{id}/status`
- **Request:** either (a) an event kind `segment_progress` with `{segment, phase: "searching"|"searched", done, total}` in `events[]`, or (b) a `progress` block in the status response: `{molecules_done, molecules_total, per_segment: {segment: "waiting"|"searching"|"searched"}}`.
- **Consumed as:** step-4 bar fill ("12 of 25 molecules searched"), per-row status while running, indeterminate→determinate progress.
- **UI fallback (shipping):** indeterminate bar on step 4; every molecule row shows "Waiting" → "Searching databases…" (step active) → "Searched" (step done).
- **Note:** the pipeline already tracks per-segment completion internally (results are written per segment); this is exposure, not new bookkeeping.

## G3 — Copies per segment and display names

- **Endpoint:** `GET /api/v1/runs/{id}/molecules` → extend `segment_meta[segment]`.
- **Request:** add `copies: int` (the loader's `molecule_count` per `__vN` variant, `src_new/loader/universe_facade.py:494-500`) and `display_name: str` (already-normalized: "Chain A", "POPC" — so the UI can drop its `seg_N_…__vN` munging), plus `chain: str | null`.
- **Consumed as:** the `×358` copy counts (list rows, group headers, eyebrow line), total atom count, identification-group copy sums.
- **UI fallback (shipping):** copies hidden (never a wrong `×1` for everything); display name derived client-side by stripping `seg_N_` / `__vN` and parsing `_chain_X` suffixes.
- **Adjacent known issue:** the loader reports lipids (e.g. POPC) as `unknown`; the page shows "Other" until the pipeline classification improves. Not blocking.

## G4 — Warnings carry no segment

- **Endpoint:** `GET /api/v1/runs/{id}/status` → `warnings[]` (`WarningItem.details`, currently `{}`)
- **Request:** populate `details` with at least `{segment: string, service: string}` when the warning originates from a resolver/generator for a specific segment. (`service` today is only recoverable by parsing the text before the first ` (` in `message`.)
- **Consumed as:** "Affects" chips on notes, per-molecule note counts, note dedup by `(code, service)`.
- **UI fallback (shipping):** notes without "Affects" lines; service parsed from message text.
- **Effort:** small (warning sites pass segment through).

## G5 — Hit names on verified hits ← biggest UX gap

- **Endpoint:** `GET /api/v1/runs/{id}/verification` → `VerifiedHitItem` (`src_new/api/models.py:223-254`)
- **Request:** add `name: str | null` (entry name from the source database record, e.g. "Sodium/potassium-transporting ATPase subunit alpha-1") and `organism: str | null` for macromolecular databases (PDB/UniProt/AlphaFold). The scorers already fetch these records during verification, so this is a passthrough, not a new lookup.
- **Consumed as:** the answer header title ("what it is"), every row line 2 in the molecule list, the "What it is" column of the matches table, identification grouping.
- **UI fallback (shipping):** the DB + ID itself as the name ("PDB 5HVX"). Usable, but it is the main thing users came for.

## G6 — Run-level CSV download

- **Endpoint (new):** `GET /api/v1/runs/{id}/download/results.csv`
- **Request:** one row per molecule (segment): label, kind, copies, identified name, best DB, best ID, confidence, confidence label, top-3 alternative IDs. No internal column names (`seg_`, resolver names) in the header.
- **Consumed as:** primary download button "Results table (CSV)".
- **UI fallback (shipping):** CSV button hidden; only "All results (JSON)" shown.

## G7 — `unique_molecules` key collision (FYI, not blocking)

- Observed 2026-10-24 on run `9d90d777` (NavMs): `/molecules` `unique_molecules` lists chain A only although chains B–D are identical. Looks like a key collision when building the map.
- The redesign does not consume `unique_molecules`, so no action needed for us — flagged for the API owner.

## G8 — Typical duration per system class

- For the "usually takes 30–120 min" facts line. Any deployment-config value (per system class or a single global range) is fine.
- **UI fallback (shipping):** the line is omitted when no value is configured.

## G9 — Per-molecule selector into the system mmCIF

- **Endpoint:** `GET /api/v1/runs/{id}/render`
- **Request:** per segment, a selector usable in the system mmCIF — atom-index ranges, or `label_asym_id` + residue ranges. Today the response carries file paths only, and highlighting by chain ID fails for virtual segments (`__vN`, e.g. lipids split across copies).
- **Consumed as:** viewer highlight/focus of any molecule; color-by-confidence per molecule in 3D.
- **UI fallback (shipping):** highlight by chain ID where it works; overlay the segment's own mmCIF for virtual segments.

---

## Contract stability requests

1. All additions must be **additive-only** (no field renames/removals) — the UI consumes the API via generated OpenAPI types plus explicitly-declared additive extensions (see `src/features/results/hooks.ts`, e.g. `RenderPathsV37`).
2. When a gap lands, bump the additive version marker so the UI can feature-detect instead of sniffing shapes.
3. Please keep `database_url` populated — the new UI links out (PDB ↗) and currently relies on it.
