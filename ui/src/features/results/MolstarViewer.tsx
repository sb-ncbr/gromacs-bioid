import React, { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "@e-infra/design-system";
import { Viewer } from "molstar/lib/apps/viewer/app";
import type { PluginUIContext } from "molstar/lib/mol-plugin-ui/context";
import { MVSData } from "molstar/lib/extensions/mvs/mvs-data";
import { loadMVS } from "molstar/lib/extensions/mvs/load";
import "molstar/build/viewer/molstar.css";
import type { RenderPathsResponse, SegmentMeta } from "./hooks";

export interface MolstarViewerProps {
  runId: string;
  segment: string;
  segments: string[];
  segmentMeta: Record<string, SegmentMeta> | null;
  renderPaths: RenderPathsResponse | null;
}

const LOAD_TIMEOUT_MS = 25000;

type ViewerMode = "loading" | "interactive" | "static" | "unavailable";

const MolstarViewer: React.FC<MolstarViewerProps> = ({
  runId,
  segment,
  segments,
  segmentMeta,
  renderPaths,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pluginRef = useRef<PluginUIContext | null>(null);
  const generationRef = useRef(0);
  const [mode, setMode] = useState<ViewerMode>("loading");
  const [ready, setReady] = useState(false);

  // Create the Mol* plugin exactly once on mount.
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
      if (viewer) {
        try {
          viewer.plugin.dispose();
        } catch {
          /* ignore dispose errors on unmount */
        }
      }
      pluginRef.current = null;
    };
  }, []);

  const fileUrl = useCallback(
    (path: string) =>
      `/files/${encodeURIComponent(runId)}/${path
        .split("/")
        .map(encodeURIComponent)
        .join("/")}`,
    [runId],
  );

  const pngUrl = `/files/${encodeURIComponent(runId)}/render/system.png`;

  // Build and load MVS for the current segment whenever dependencies change.
  useEffect(() => {
    if (!ready || !pluginRef.current || !renderPaths) return;

    const gen = ++generationRef.current;
    setMode("loading");

    const file: string | null =
      segment === "SYSTEM"
        ? renderPaths.system_mmcif ?? null
        : (renderPaths.segments?.[segment] ?? renderPaths.system_mmcif ?? null);

    const checkStatic = async (): Promise<boolean> => {
      try {
        const res = await fetch(pngUrl, { method: "HEAD" });
        return res.ok;
      } catch {
        return false;
      }
    };

    // No structural data at all → check static render.
    if (!file) {
      checkStatic().then((ok) => {
        if (gen === generationRef.current) setMode(ok ? "static" : "unavailable");
      });
      return;
    }

    let cancelled = false;

    const load = async (): Promise<void> => {
      const plugin = pluginRef.current;
      if (!plugin) return;

      const builder = MVSData.createBuilder();
      const url = fileUrl(file!);
      const structure = builder
        .download({ url })
        .parse({ format: "mmcif" })
        .modelStructure();

      const segList = Array.isArray(segments) ? segments : [];
      for (const seg of segList) {
        const meta = segmentMeta?.[seg] ?? null;
        const isProtein = meta?.type === "protein";
        const isSelected = segment === "SYSTEM" || seg === segment;
        structure
          .component({ selector: { auth_asym_id: seg } })
          .representation({
            type: isProtein ? "cartoon" : "ball_and_stick",
          })
          .opacity({ opacity: isSelected ? 1.0 : 0.15 });
      }

      await loadMVS(plugin, builder.getState(), {
        appendSnapshots: false,
        keepCamera: true,
        sanityChecks: true,
      });
    };

    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("Mol* load timeout")), LOAD_TIMEOUT_MS),
    );

    const loadPromise = load()
      .then(() => {
        if (!cancelled && gen === generationRef.current) setMode("interactive");
      })
      .catch(async (err: unknown) => {
        console.warn("Mol* structure load failed:", err);
        if (cancelled || gen !== generationRef.current) return;
        const ok = await checkStatic();
        if (gen === generationRef.current) setMode(ok ? "static" : "unavailable");
      });

    Promise.race([loadPromise, timeout]).catch(async (err: unknown) => {
      if (cancelled || gen !== generationRef.current) return;
      console.warn("Mol* load timed out, falling back to static render:", err);
      const ok = await checkStatic();
      if (gen === generationRef.current) setMode(ok ? "static" : "unavailable");
    });

    return () => {
      cancelled = true;
    };
  }, [ready, runId, segment, segments, segmentMeta, renderPaths, fileUrl, pngUrl]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Structure viewer — {segment === "SYSTEM" ? "whole system" : `segment ${segment}`}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative h-96 w-full overflow-hidden rounded-lg">
          {/* Mol* container – always mounted to keep WebGL context alive */}
          <div
            ref={containerRef}
            className="absolute inset-0 h-full w-full"
            style={{
              opacity: mode === "interactive" ? 1 : 0,
              pointerEvents: mode === "interactive" ? "auto" : "none",
            }}
          />

          {mode === "loading" && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
              <Skeleton className="h-4 w-40" />
              <p className="mt-3 text-sm text-text-muted">Loading 3D structure…</p>
            </div>
          )}

          {mode === "static" && (
            <div className="absolute inset-0 bg-white">
              <img
                src={pngUrl}
                alt="Static molecular rendering"
                className="h-full w-full object-contain"
              />
              <p className="absolute bottom-2 left-0 right-0 text-center text-xs text-text-muted">
                Static rendering (interactive view unavailable)
              </p>
            </div>
          )}

          {mode === "unavailable" && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
              <p className="text-sm text-text-muted">Structural data not available</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default MolstarViewer;
