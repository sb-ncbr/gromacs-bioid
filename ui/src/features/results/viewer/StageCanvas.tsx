/**
 * StageCanvas — the Mol* canvas of the stage card (SPEC.md §3.5b).
 *
 * Kept from the legacy viewer: create-once plugin, 25 s load watchdog,
 * geometry pre-flight (server flag v3.139 or client probe), the 1M-atom
 * static-render gate with opt-in, static/unavailable fallbacks.
 *
 * New: scenes come from viewerModel.planScene (one component per kind,
 * A6 fix); highlight / by-confidence modes; water+ions, reset and
 * full-screen controls floating on the canvas; legend pill; two-way
 * chain selection; camera focus on selection (G9 note: chain-addressable
 * molecules only until the backend exposes per-segment selectors).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Toggle, ToggleGroup, ToggleGroupItem, Tooltip, TooltipContent, TooltipTrigger, Skeleton } from "@e-infra/design-system";
import { Maximize, RotateCcw, Droplet } from "lucide-react";
import { Viewer } from "molstar/lib/apps/viewer/app";
import type { PluginUIContext } from "molstar/lib/mol-plugin-ui/context";
import { buildMvs } from "./mvsScene";
import { loadMVS } from "molstar/lib/extensions/mvs/load";
import "molstar/build/viewer/molstar.css";
import type { Molecule, RunStatus } from "../viewmodel";
import type { RenderPathsResponse, RenderPathsV37, RenderPathsV39 } from "../hooks";
import { isOverInteractivityGate, resolveStaticPngPath } from "../utils/static-render";
import { probeStructureGeometry } from "../utils/geometry-check";
import {
  LIGHT_PALETTE,
  planScene,
  moleculeForChain,
  type CanvasMode,
  type Palette,
} from "./viewerModel";

const LOAD_TIMEOUT_MS = 25000;

export interface StageCanvasProps {
  runId: string;
  runStatus: RunStatus;
  molecules: Molecule[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  renderPaths: RenderPathsResponse | null;
  /** Segment id used for the static-PNG fallback (same as today). */
  fallbackSegment?: string;
  /** Initial colouring; the whole-system view opens by confidence. */
  defaultMode?: CanvasMode;
}

type Mode = "loading" | "interactive" | "static" | "unavailable";

/** Resolve the handoff palette from the themed CSS custom properties. */
function readPalette(): Palette {
  const cs = getComputedStyle(document.documentElement);
  const take = (name: string, fallback: string) => cs.getPropertyValue(name).trim() || fallback;
  return {
    high: take("--vm-high", LIGHT_PALETTE.high),
    medium: take("--vm-medium", LIGHT_PALETTE.medium),
    low: take("--vm-low", LIGHT_PALETTE.low),
    none: take("--vm-none", LIGHT_PALETTE.none),
    accent: take("--vm-accent", LIGHT_PALETTE.accent),
    other: take("--vm-scene-other", LIGHT_PALETTE.other),
    water: take("--vm-scene-water", LIGHT_PALETTE.water),
    ion: take("--vm-scene-ion", LIGHT_PALETTE.ion),
  };
}

export function StageCanvas({ runId, runStatus, molecules, selectedId, onSelect, renderPaths, fallbackSegment = "SYSTEM", defaultMode = "highlight" }: StageCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pluginRef = useRef<PluginUIContext | null>(null);
  const generationRef = useRef(0);
  const [mode, setMode] = useState<Mode>("loading");
  const [ready, setReady] = useState(false);
  const [forceInteractive, setForceInteractive] = useState(false);
  const [canvasMode, setCanvasMode] = useState<CanvasMode>(defaultMode);
  const [showWaterIons, setShowWaterIons] = useState(false);

  const finished = runStatus === "finished";

  // Create the Mol* plugin exactly once (unchanged from the legacy viewer).
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let cancelled = false;
    let viewer: Viewer | null = null;
    (async () => {
      try {
        const v = await Viewer.create(el, {
          layoutIsExpanded: false,
          layoutShowControls: false,
          layoutShowLeftPanel: false,
          layoutShowSequence: false,
          layoutShowLog: false,
        });
        if (cancelled) {
          v.plugin.dispose();
          return;
        }
        viewer = v;
        pluginRef.current = v.plugin;
        setReady(true);
      } catch (err) {
        console.error("Mol* plugin creation failed:", err);
      }
    })();
    return () => {
      cancelled = true;
      try {
        viewer?.plugin.dispose();
      } catch {
        /* ignore dispose errors */
      }
      pluginRef.current = null;
    };
  }, []);

  // Two-way selection: Mol* chain click → molecule selection (G9 note).
  useEffect(() => {
    const plugin = pluginRef.current;
    if (!ready || !plugin) return;
    const sub = plugin.behaviors.interaction.click.subscribe(({ current }) => {
      void (async () => {
        try {
          const { StructureElement, StructureProperties: SP } = await import("molstar/lib/mol-model/structure");
          const loci = current.loci;
          if (loci.kind !== "element-loci") return;
          const first = loci.elements[0];
          if (!first) return;
          const loc = StructureElement.Location.create(loci.structure, first.unit, first.unit.elements[0]);
          const asym = SP.chain.auth_asym_id(loc);
          const id = moleculeForChain(molecules, asym ?? null);
          if (id && id !== selectedId) onSelect(id);
        } catch {
          /* clicking empty space or unmapped residues: ignore */
        }
      })();
    });
    return () => sub.unsubscribe();
  }, [ready, molecules, selectedId, onSelect]);

  const v37 = (renderPaths ?? null) as (RenderPathsResponse & RenderPathsV37) | null;
  const v39 = (renderPaths ?? null) as (RenderPathsResponse & RenderPathsV39) | null;
  const totalAtoms = v37?.total_atom_count ?? null;
  const overGate = isOverInteractivityGate(totalAtoms);
  const file: string | null = renderPaths?.system_mmcif ?? null;

  const fileUrl = useCallback(
    (path: string) => `/files/${encodeURIComponent(runId)}/${path.split("/").map(encodeURIComponent).join("/")}`,
    [runId],
  );
  const pngUrl = fileUrl(resolveStaticPngPath(v37, fallbackSegment));

  const plan = useMemo(
    () => planScene(molecules, runStatus, canvasMode, selectedId, showWaterIons, readPalette()),
    [molecules, runStatus, canvasMode, selectedId, showWaterIons],
  );

  // Rebuild the scene when the plan or structure changes; camera is kept so
  // selection-driven updates don't reset the view (a real reload happens
  // only when the run's structure changes, per SPEC.md §3.5b + G9 follow-up:
  // use destructive-free overpaint once per-segment selectors exist).
  useEffect(() => {
    if (!ready || !pluginRef.current) return;
    const gen = ++generationRef.current;
    setMode("loading");

    const checkStatic = async (): Promise<boolean> => {
      try {
        return (await fetch(pngUrl, { method: "HEAD" })).ok;
      } catch {
        return false;
      }
    };

    if (overGate && !forceInteractive) {
      void checkStatic().then((ok) => gen === generationRef.current && setMode(ok ? "static" : "unavailable"));
      return;
    }
    if (!file) {
      void checkStatic().then((ok) => gen === generationRef.current && setMode(ok ? "static" : "unavailable"));
      return;
    }

    let cancelled = false;
    const url = fileUrl(file);

    const load = async (): Promise<void> => {
      const plugin = pluginRef.current!;
      if (v39?.geometry) {
        if (v39.geometry.status === "degenerate") {
          console.warn("Mol*: skipping interactive load, degenerate geometry (server flag)");
          const ok = await checkStatic();
          if (!cancelled && gen === generationRef.current) setMode(ok ? "static" : "unavailable");
          return;
        }
      } else if (generationRef.current === gen) {
        try {
          const res = await fetch(url);
          const probe = probeStructureGeometry(await res.text());
          if (probe.status === "degenerate") {
            const ok = await checkStatic();
            if (!cancelled && gen === generationRef.current) setMode(ok ? "static" : "unavailable");
            return;
          }
        } catch {
          /* proceed with the load */
        }
      }
      await loadMVS(plugin, buildMvs(url, plan.components), {
        appendSnapshots: false,
        keepCamera: true,
        sanityChecks: true,
      });
    };

    const timeout = new Promise<never>((_, reject) => setTimeout(() => reject(new Error("Mol* load timeout")), LOAD_TIMEOUT_MS));
    void Promise.race([load(), timeout]).catch(async () => {
      if (cancelled || gen !== generationRef.current) return;
      const ok = await checkStatic();
      if (gen === generationRef.current) setMode(ok ? "static" : "unavailable");
    }).then(() => {
      void 0; // mode set by the load/catch paths
    });
    void load()
      .then(() => !cancelled && gen === generationRef.current && setMode("interactive"))
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, plan, file, forceInteractive, overGate, fileUrl, pngUrl]);

  const resetView = () => {
    try {
      pluginRef.current?.managers.camera.reset();
    } catch {
      /* no scene yet */
    }
  };
  const fullScreen = () => {
    const el = containerRef.current?.closest("[data-stage-canvas]");
    void el?.requestFullscreen?.();
  };

  const noStructureYet = !file && runStatus !== "finished" && runStatus !== "failed";
  const interactive = mode === "interactive";

  return (
    <div
      data-stage-canvas
      className="relative w-full overflow-hidden rounded-lg bg-(--vm-viewer-bg) h-[clamp(440px,66vh,720px)] max-lg:aspect-square max-lg:h-auto"
    >
      {/* Mol* container — always mounted to keep the WebGL context alive */}
      <div
        ref={containerRef}
        className="absolute inset-0 h-full w-full"
        style={{ opacity: interactive ? 1 : 0, pointerEvents: interactive ? "auto" : "none" }}
      />

      {/* Controls: top-left colour mode, top-right actions, bottom-left legend */}
      <div className="absolute left-3 top-3 z-10">
        <ToggleGroup
          type="single"
          value={canvasMode}
          onValueChange={(v) => v && setCanvasMode(v as CanvasMode)}
          className="rounded-md border border-(--vm-line) bg-white/90 p-0.5 text-xs shadow-sm dark:bg-(--vm-surface-2)"
        >
          <ToggleGroupItem value="highlight" className="px-2 py-1 text-xs" aria-label="Highlight selected molecule">
            Highlight
          </ToggleGroupItem>
          <ToggleGroupItem value="confidence" disabled={!finished || !interactive} className="px-2 py-1 text-xs" aria-label="Colour by confidence">
            By confidence
          </ToggleGroupItem>
        </ToggleGroup>
      </div>
      <div className="absolute right-3 top-3 z-10 flex gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Toggle
              size="sm"
              pressed={showWaterIons}
              onPressedChange={setShowWaterIons}
              aria-label={showWaterIons ? "Hide water and ions" : "Show water and ions"}
              className="size-[34px] border border-(--vm-line) bg-white/90 dark:bg-(--vm-surface-2)"
            >
              <Droplet size={16} aria-hidden />
            </Toggle>
          </TooltipTrigger>
          <TooltipContent>{showWaterIons ? "Hide water and ions" : "Show water and ions"}</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label="Reset view"
              onClick={resetView}
              className="flex size-[34px] items-center justify-center rounded-md border border-(--vm-line) bg-white/90 dark:bg-(--vm-surface-2)"
            >
              <RotateCcw size={16} aria-hidden />
            </button>
          </TooltipTrigger>
          <TooltipContent>Reset view</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label="Full screen"
              onClick={fullScreen}
              className="flex size-[34px] items-center justify-center rounded-md border border-(--vm-line) bg-white/90 dark:bg-(--vm-surface-2)"
            >
              <Maximize size={16} aria-hidden />
            </button>
          </TooltipTrigger>
          <TooltipContent>Full screen</TooltipContent>
        </Tooltip>
      </div>
      {interactive && (
        <div className="absolute bottom-3 left-3 z-10 flex items-center gap-3 rounded-full border border-(--vm-line) bg-white/90 px-3 py-1 text-xs text-(--vm-fg-2) shadow-sm dark:bg-(--vm-surface-2)">
          {plan.legend.map((l) => (
            <span key={l.label} className="inline-flex items-center gap-1.5">
              <span className="inline-block size-2.5 rounded-full" style={{ backgroundColor: l.colorHex }} aria-hidden />
              {l.label}
            </span>
          ))}
        </div>
      )}

      {/* States */}
      {mode === "loading" && !noStructureYet && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
          <Skeleton className="h-4 w-40" />
          <p className="text-sm text-(--vm-muted)">Loading 3D structure…</p>
        </div>
      )}
      {noStructureYet && mode === "loading" && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-sm text-(--vm-muted)">The 3D view appears once your files have been read.</p>
        </div>
      )}
      {mode === "static" && (
        <div className="absolute inset-0">
          <img src={pngUrl} alt="Static molecular rendering" className="h-full w-full object-contain" />
          {overGate && !forceInteractive && (
            <div className="absolute inset-0 flex items-center justify-center">
              <button
                type="button"
                onClick={() => setForceInteractive(true)}
                className="rounded-full border border-(--vm-line) bg-white/95 px-4 py-2 text-sm font-medium text-(--vm-fg) shadow-sm hover:bg-(--vm-surface-2)"
              >
                Load interactive 3D view (large system, may be slow)
              </button>
            </div>
          )}
        </div>
      )}
      {mode === "unavailable" && (
        <div className="absolute inset-0 flex items-center justify-center px-4">
          <p className="text-sm text-(--vm-muted)">
            Structural data not available
            {overGate ? ` (${totalAtoms!.toLocaleString()} atoms)` : ""}
          </p>
        </div>
      )}
    </div>
  );
}

export default StageCanvas;
