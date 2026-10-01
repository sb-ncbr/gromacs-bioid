import React from "react";
import {
  Network,
  Dna,
  Layers,
  Hexagon,
  Droplet,
  Zap,
  Atom,
  Shapes,
  Boxes,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@e-infra/design-system";

/** Molecule-type -> lucide icon (CONTEXT map; unknown falls back to Shapes). */
const TYPE_ICON: Record<string, LucideIcon> = {
  protein: Network,
  nucleic: Dna,
  lipid: Layers,
  carbohydrate: Hexagon,
  water: Droplet,
  solvent: Droplet,
  ion: Zap,
  small_molecule: Atom,
  other: Shapes,
  unknown: Shapes,
};

export interface SegmentMeta {
  type?: string | null;
  atom_count?: number | null;
  residue_count?: number | null;
}

export interface MoleculeSelectorProps {
  /** Segment names, e.g. ["A","B","C","D"]. */
  segments: string[];
  /** Per-segment metadata (type, atom_count, residue_count). */
  segmentMeta?: Record<string, SegmentMeta> | null;
  /** Currently selected segment; "SYSTEM" means the whole system. */
  selected: string;
  /** Emit the chosen segment id (parent handles navigation). */
  onSelect: (segment: string) => void;
}

function typeLabel(type: string | null | undefined): string {
  if (!type) return "unknown";
  return type;
}

function iconFor(type: string | null | undefined): LucideIcon {
  return TYPE_ICON[type || ""] ?? Shapes;
}

const MoleculeSelector: React.FC<MoleculeSelectorProps> = ({
  segments,
  segmentMeta,
  selected,
  onSelect,
}) => {
  const meta = segmentMeta || {};
  const segs = Array.isArray(segments) ? segments : [];

  const options: { id: string; label: string; atoms: number | null }[] = [
    { id: "SYSTEM", label: "Whole system", atoms: null },
    ...segs.map((s) => ({
      id: s,
      label: `${s} \u00b7 ${typeLabel(meta[s]?.type)}`,
      atoms: (meta[s]?.atom_count as number | undefined) ?? null,
    })),
  ];

  return (
    <div className="flex flex-col gap-1" role="listbox" aria-label="Molecule segments">
      {options.map((opt) => {
        const Icon = opt.id === "SYSTEM" ? Boxes : iconFor(meta[opt.id]?.type);
        const active = selected === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            role="option"
            aria-selected={active}
            onClick={() => onSelect(opt.id)}
            className={cn(
              "flex items-center gap-3 rounded-md border px-3 py-2 text-left text-sm transition-colors",
              active
                ? "border-[#2E7D32] bg-[#2E7D32]/10 text-[#1b5e20] font-medium"
                : "border-gray-200 bg-white text-gray-700 hover:bg-gray-50",
            )}
          >
            <Icon
              size={18}
              className={active ? "text-[#2E7D32]" : "text-gray-500"}
              aria-hidden
            />
            <span className="flex-1 truncate">{opt.label}</span>
            {opt.atoms != null && (
              <span className="text-xs tabular-nums text-gray-400">
                {opt.atoms} atoms
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

export default MoleculeSelector;
