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

export type Representation = "cartoon" | "ball_and_stick" | "licorice" | "spacefill" | "point";

export interface PlanComponent {
  key: string;
  /** Mol* built-in selector (protein/ligand/water/ion…) or one auth chain. */
  builtin?: "protein" | "nucleic" | "ligand" | "water" | "ion" | "non_standard";
  chainAsymId?: string;
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
  water: "point",
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
  if (kinds.has("lipid") || kinds.has("unknown")) {
    out.push({ key: "kind:other", builtin: "non_standard", representation: "ball_and_stick", colorHex: p.other });
  }
  return out;
}

/**
 * Build the scene plan.
 * - highlight: everything neutral, the selected molecule's chain in accent.
 * - confidence: every chain-addressable molecule in its label colour.
 */
export function planScene(
  molecules: Molecule[],
  runStatus: RunStatus,
  mode: CanvasMode,
  selectedId: string | null,
  showWaterIons: boolean,
  palette: Palette = LIGHT_PALETTE,
): ScenePlan {
  const components = basePlan(molecules, showWaterIons, palette);
  const effective: CanvasMode = runStatus === "finished" ? mode : "highlight";

  if (effective === "confidence") {
    for (const m of molecules) {
      if (m.chain == null) continue; // G9: no selector for virtual segments
      if ((m.kind === "water" || m.kind === "ion") && !showWaterIons) continue;
      components.push({
        key: `mol:${m.id}`,
        chainAsymId: m.chain,
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
  if (selected?.chain != null) {
    components.push({
      key: `sel:${selected.id}`,
      chainAsymId: selected.chain,
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
export function moleculeForChain(molecules: Molecule[], asymId: string | null): string | null {
  if (asymId == null) return null;
  return molecules.find((m) => m.chain === asymId)?.id ?? null;
}
