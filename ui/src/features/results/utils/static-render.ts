/**
 * Static-render path resolution + interactivity gate (pure, v3.137).
 *
 * Mol* default view can be too slow for huge systems, so the UI:
 *  1. defaults to a static PNG when total atoms >= ATOM_INTERACTIVE_LIMIT
 *     (with a user "load anyway" opt-in in the component);
 *  2. falls back to a static PNG whenever Mol* fails/times out.
 * Both decisions depend ONLY on data from GET /runs/{id}/render, so they
 * live here as pure functions (see tests in static-render.test.ts).
 */

import type { RenderPathsResponse, RenderPathsV37 } from "../hooks";
import { ATOM_INTERACTIVE_LIMIT } from "../hooks";

type RenderPathsLike = (Partial<RenderPathsResponse> & RenderPathsV37) | null | undefined;

/** Legacy fallback used before the API recorded render paths (pre-v3.137 runs). */
export const STATIC_PNG_LEGACY_PATH = "render/system.png";

/** Whole-system atom counts >= this switch the default to static. */
export const SYSTEM_ATOM_LIMIT = ATOM_INTERACTIVE_LIMIT;

export function isOverInteractivityGate(totalAtoms: number | null | undefined,
                                        limit: number = SYSTEM_ATOM_LIMIT): boolean {
  return totalAtoms != null && totalAtoms >= limit;
}

/**
 * Which static PNG path (relative to the run dir) should back the given view?
 * Priority: per-segment PNG → system PNG from the API → legacy default path.
 */
export function resolveStaticPngPath(renderPaths: RenderPathsLike,
                                     segment: string): string {
  const segmentPng =
    segment !== "SYSTEM" ? renderPaths?.segment_pngs?.[segment] ?? null : null;
  return segmentPng ?? renderPaths?.system_png ?? STATIC_PNG_LEGACY_PATH;
}
