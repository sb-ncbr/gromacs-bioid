import { MVSData } from "molstar/lib/extensions/mvs/mvs-data";
import type { PlanComponent } from "./viewerModel";

/**
 * Build one MVS state from the scene plan.
 *
 * Every component, representation and colour value must be one MVS accepts:
 * a single invalid parameter fails MVS validation for the whole scene and the
 * viewer shows "Structural data not available" (live 2026-11-06: colour was
 * passed as `hex`, water as "point", lipids as selector "non_standard").
 */
export function buildMvs(url: string, components: PlanComponent[]) {
  const builder = MVSData.createBuilder();
  const structure = builder.download({ url }).parse({ format: "mmcif" }).modelStructure();
  for (const c of components) {
    const selector = c.builtin
      ? c.builtin
      : c.residueRanges
        ? c.residueRanges.map(([auth_asym_id, beg_auth_seq_id, end_auth_seq_id]) => ({
            auth_asym_id,
            beg_auth_seq_id,
            end_auth_seq_id,
          }))
        : c.atomIndices
          ? c.atomIndices.map((atom_index) => ({ atom_index }))
          : { auth_asym_id: c.chainAsymId ?? "" };
    structure
      .component({ selector })
      .representation({ type: c.representation })
      .color({ color: c.colorHex as `#${string}` });
  }
  return builder.getState();
}
