/**
 * Mol* canvas model (SPEC.md §3.5b) — pure scene planning: kind groups,
 * colour modes, legend. No Mol* imports here; StageCanvas executes the plan.
 *
 * Gap G9 note: there is no per-segment selector into the system mmCIF in
 * today's /render, so per-molecule colouring works for chain-addressable
 * molecules (proteinnucleic chains, single-residue ligands by chain).
 * Virtual segments (__vN lipids/ions/water) share the neutral base until
 * the backend exposes a selector — never a wrong highlight.
 */
import type { Molecule, MoleculeKind, RunStatus } from "../viewmodel";
import { bucketOf } from "../list";

export type CanvasMode = "highlight" | "confidence";

/** Theme palette resolved from the CSS custom properties at runtime. */
export interface Palette {
  high: string;
  medium: string;
  low: string;
  none: string;
  accent: string;
  other: string;
  water: string;
  ion: string;
}

export const LIGHT_PALETTE: Palette = {
  high: "#1f5f26",
  medium: "#b07508",
  low: "#6b7480",
  none: "#9a3412",
  accent: "#1f5f26",
  other: "#c3c9d0",
  water: "#9cc0e4",
  ion: "#8a6fc0",
};

/** MVS representation types (molstar mvs-tree-representations; no "point"/"licorice"). */
export type Representation = "cartoon" | "ball_and_stick" | "spacefill";

/** G9: per-segment selector into the system mmCIF (`/render` segment_selectors). */
export interface SegmentSelector {
  chains: string[];
  /** 0-based [start, end) atom_site rows (MVS atom_index). */
  atom_index_ranges: number[][];
  atom_count: number;
  /** All copies as inclusive [chain, beg_auth_seq_id, end_auth_seq_id]
   * ranges; exact (no foreign residue inside), absent when numbers clash. */
  residue_ranges?: [string, number, number][] | null;
}
export type SegmentSelectors = Record<string, SegmentSelector>;

/** Virtual segments share their parent's chain; above this many atoms they
 * are not addressed atom by atom (bulk water/lipids stay neutral). */
export const ATOM_INDEX_CAP = 5000;
/** Residue ranges are compact (one per contiguous run of copies); above
 * this many the molecule is too fragmented to address that way. */
export const RESIDUE_RANGE_CAP = 2000;

export interface PlanComponent {
  key: string;
  /** Mol* built-in selector (protein/ligand/water/ion…) or one auth chain. */
  /** MVS ComponentSelectorT values only — an unknown one fails MVS validation and the whole scene. */
  builtin?: "protein" | "nucleic" | "ligand" | "water" | "ion";
  chainAsymId?: string;
  /** G9 fallback for segments without their own chain: MVS atom_index list. */
  atomIndices?: number[];
  /** G9: every copy as auth_seq_id ranges [chain, beg, end] (inclusive). */
  residueRanges?: [string, number, number][];
  representation: Representation;
  colorHex: string;
}

/** Kind → representation (SPEC.md §3.5b). */
export const KIND_REPRESENTATION: Record<MoleculeKind, Representation> = {
  protein: "cartoon",
  nucleic: "cartoon",
  small_molecule: "ball_and_stick",
  lipid: "ball_and_stick", // thin licorice once stylable through MVS size params
  ion: "spacefill",
  water: "ball_and_stick",
  unknown: "ball_and_stick",
};

/** Kind → built-in MVS selector covering it (one component per kind, A6 fix). */
const KIND_BUILTIN: Partial<Record<MoleculeKind, PlanComponent["builtin"]>> = {
  protein: "protein",
  nucleic: "nucleic",
  small_molecule: "ligand",
  ion: "ion",
  water: "water",
};

function kindColor(kind: MoleculeKind, p: Palette): string {
  if (kind === "water") return p.water;
  if (kind === "ion") return p.ion;
  return p.other;
}

function labelColor(m: Molecule, p: Palette): string {
  const b = bucketOf(m, "finished");
  if (b === "high") return p.high;
  if (b === "medium") return p.medium;
  if (b === "low") return p.low;
  return p.none;
}

export interface ScenePlan {
  components: PlanComponent[];
  legend: { label: string; colorHex: string }[];
}

function basePlan(molecules: Molecule[], showWaterIons: boolean, p: Palette): PlanComponent[] {
  const kinds = new Set(molecules.map((m) => m.kind));
  const out: PlanComponent[] = [];
  for (const [kind, builtin] of Object.entries(KIND_BUILTIN) as [MoleculeKind, PlanComponent["builtin"] & string][]) {
    if (!kinds.has(kind)) continue;
    if ((kind === "water" || kind === "ion") && !showWaterIons) continue;
    out.push({
      key: `kind:${kind}`,
      builtin,
      representation: KIND_REPRESENTATION[kind],
      colorHex: kindColor(kind, p),
    });
  }
  // Lipids/unknown non-polymers fall under MVS "ligand"; drawn once, in the
  // same neutral colour as small molecules, unless that component exists.
  if ((kinds.has("lipid") || kinds.has("unknown")) && !kinds.has("small_molecule")) {
    out.push({ key: "kind:other", builtin: "ligand", representation: "ball_and_stick", colorHex: p.other });
  }
  return out;
}

const VIRTUAL = /__v\d+$/;

/**
 * Where a molecule is in the system mmCIF, every copy of it: the G9 residue
 * ranges when present (exact, compact — and unlike a chain they never paint
 * the ligands/water sharing that chain), else its own chain (parsed
 * `_chain_X` name, or the selector's single chain for a non-virtual
 * segment), else its atom rows when small enough; null when not addressable.
 */
export function addressOf(
  m: Molecule,
  selectors?: SegmentSelectors | null,
): Pick<PlanComponent, "chainAsymId" | "atomIndices" | "residueRanges"> | null {
  const sel = selectors?.[m.id];
  const ranges = sel?.residue_ranges;
  if (ranges && ranges.length > 0 && ranges.length <= RESIDUE_RANGE_CAP) return { residueRanges: ranges };
  if (m.chain != null) return { chainAsymId: m.chain };
  if (!sel) return null;
  if (!VIRTUAL.test(m.id) && sel.chains.length === 1) return { chainAsymId: sel.chains[0] };
  if (sel.atom_count > 0 && sel.atom_count <= ATOM_INDEX_CAP) {
    const atomIndices: number[] = [];
    for (const [beg, end] of sel.atom_index_ranges) for (let i = beg; i < end; i++) atomIndices.push(i);
    return atomIndices.length ? { atomIndices } : null;
  }
  return null;
}

/**
 * Build the scene plan.
 * - highlight: everything neutral, the selected molecule's chain in accent.
 * - confidence: every addressable molecule in its label colour.
 * Molecules are addressed by chain, else through the G9 selectors.
 */
export function planScene(
  molecules: Molecule[],
  runStatus: RunStatus,
  mode: CanvasMode,
  selectedId: string | null,
  showWaterIons: boolean,
  palette: Palette = LIGHT_PALETTE,
  selectors?: SegmentSelectors | null,
): ScenePlan {
  const components = basePlan(molecules, showWaterIons, palette);
  const effective: CanvasMode = runStatus === "finished" ? mode : "highlight";

  if (effective === "confidence") {
    for (const m of molecules) {
      if ((m.kind === "water" || m.kind === "ion") && !showWaterIons) continue;
      const address = addressOf(m, selectors);
      if (!address) continue;
      components.push({
        key: `mol:${m.id}`,
        ...address,
        representation: KIND_REPRESENTATION[m.kind],
        colorHex: labelColor(m, palette),
      });
    }
    return {
      components,
      legend: [
        { label: "High", colorHex: palette.high },
        { label: "Medium", colorHex: palette.medium },
        { label: "Low", colorHex: palette.low },
        { label: "None", colorHex: palette.none },
      ],
    };
  }

  const selected = molecules.find((m) => m.id === selectedId) ?? null;
  const legend: ScenePlan["legend"] = [];
  const selectedAddress = selected ? addressOf(selected, selectors) : null;
  if (selected && selectedAddress) {
    components.push({
      key: `sel:${selected.id}`,
      ...selectedAddress,
      representation: KIND_REPRESENTATION[selected.kind],
      colorHex: palette.accent,
    });
    legend.push({ label: selected.display_name, colorHex: palette.accent });
  }
  legend.push({ label: "Other", colorHex: palette.other });
  if (showWaterIons) {
    if (molecules.some((m) => m.kind === "water")) legend.push({ label: "Water", colorHex: palette.water });
    if (molecules.some((m) => m.kind === "ion")) legend.push({ label: "Ions", colorHex: palette.ion });
  }
  return { components, legend };
}

/**
 * Segment lookup for Mol* clicks: loci give a chain's auth_asym_id; match it
 * back to a molecule (identical chains collapse to the first — two-way
 * selection stays exact for distinct chains, see G9).
 */
export function moleculeForChain(
  molecules: Molecule[],
  asymId: string | null,
  selectors?: SegmentSelectors | null,
): string | null {
  if (asymId == null) return null;
  return (
    molecules.find((m) => m.chain === asymId)?.id ??
    molecules.find((m) => !VIRTUAL.test(m.id) && selectors?.[m.id]?.chains.length === 1 &&
      selectors[m.id].chains[0] === asymId)?.id ??
    null
  );
}
