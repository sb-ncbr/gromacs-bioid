import { useEffect, useRef, useState } from "react";
import { Box, CircularProgress, Alert } from "@mui/material";
import 'molstar/build/viewer/molstar.css';
import { Viewer } from 'molstar/lib/apps/viewer/app';
import { PluginExtensions } from 'molstar/lib/apps/viewer/app';

interface RenderPathsResponse {
    run_id: string;
    system_mmcif?: string | null;
    segments?: Record<string, string>;
}


interface MDViewerProps {
    runId: string;
    segment: string;
    segments: string[];
    width?: number | string;
    height?: number | string;
}

const MDViewer = ({
    runId,
    segment,
    segments,
    width = "100%",
    height = "100%",
}: MDViewerProps) => {

    const viewerContainerRef = useRef<HTMLDivElement | null>(null);
    
    const [loading, setLoading] = useState(false);
    const [renderData, setRenderData] = useState<RenderPathsResponse | null>(null);
    const [structureError, setStructureError] = useState<string | null>(null);
    
    // Debounce refs
    const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const prevSegmentRef = useRef<string>(segment);

    // Fetch render paths with polling when mmCIF unavailable
    useEffect(() => {
        if (!runId) return;
        let interval: ReturnType<typeof setInterval> | null = null;
        
        const fetchRenderPaths = async () => {
            try {
                const res = await fetch(`/runs/${runId}/render`);
                if (!res.ok) {
                    setStructureError("Simulation structure data could not be loaded.");
                    return;
                }
                const data: RenderPathsResponse = await res.json();
                if (!data.system_mmcif) {
                    setStructureError("No mmCIF structure file is available for this run.");
                    return;
                }
                setRenderData(data);
                setStructureError(null);
                // Stop polling once we have valid mmCIF
                if (interval) {
                    clearInterval(interval);
                    interval = null;
                }
            } catch (e) {
                console.error("Failed to fetch render paths", e);
                setStructureError("Simulation structure data could not be loaded.");
            }
        };
        
        // Initial immediate fetch
        fetchRenderPaths();
        
        // Start polling every 10 seconds if mmCIF is still missing
        interval = setInterval(() => {
            if (!renderData?.system_mmcif) {
                fetchRenderPaths();
            }
        }, 10000);
        
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [runId]);

    // Main render effect - creates new viewer on each render
    useEffect(() => {
        // Cleanup previous debounce timer
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
        }

        // Only debounce when segment changes (not on initial load or other deps change)
        const segmentChanged = prevSegmentRef.current !== segment;
        prevSegmentRef.current = segment;

        const render = async () => {
            if (!viewerContainerRef.current) return;
            if (structureError) {
                setLoading(false);
                return;
            }
            
            setLoading(true);

            try {
                // Dispose old viewer if exists to avoid leaking plugin
                if (viewerContainerRef.current) {
                    viewerContainerRef.current.innerHTML = "";
                }

                const viewer = await Viewer.create(viewerContainerRef.current, {
                    layoutIsExpanded: false,
                    layoutShowControls: false,
                });

                const builder = PluginExtensions.mvs.MVSData.createBuilder();

                // Use dynamic render path from API, fallback to hardcoded path
                const systemPath = renderData?.system_mmcif || "render/system.cif";
                // Strip leading slashes to avoid double slashes in URL
                const cleanPath = systemPath.replace(/^\/+/, '');
                const structureUrl = `/files/${runId}/${cleanPath}`;

                const structure = builder
                    .download({ url: structureUrl })
                    .parse({ format: "mmcif" })
                    .modelStructure({});

                const safeSegments = Array.isArray(segments) ? segments : [];

                // Fetch protein types inline for each segment
                const segmentData = await Promise.all(
                    safeSegments.map(async (seg) => {
                        let isProtein = false;
                        try {
                            const res = await fetch(`/runs/${runId}/verification?segment=${seg}`);
                            if (res.ok) {
                                const d = await res.json();
                                isProtein = d.hits?.some((h: any) =>
                                    h.ident_type?.toLowerCase().includes('protein') ||
                                    h.ident_type?.toLowerCase().includes('uniprot')
                                ) || false;
                            }
                        } catch (e) {
                            console.error(`Failed to fetch type for ${seg}`, e);
                        }
                        const opacity_val = segment === "SYSTEM" || segment === seg ? 1.0 : 0.15;
                        return { name: seg, isProtein, opacity_val };
                    })
                );

                // Fallback: no segment info available - show whole structure as generic cartoon
                if (safeSegments.length === 0) {
                    structure
                        .component({ selector: 'all' })
                        .representation({ type: 'cartoon' })
                        .color({ custom: { molstar_use_default_coloring: true } })
                        .opacity({ opacity: 1.0 });
                } else {
                    // Single loop: apply component + representation + color + opacity for each segment
                    for (const { name, isProtein, opacity_val } of segmentData) {
                        if (isProtein) {
                            structure
                                .component({ selector: { auth_asym_id: name } })
                                .representation({ type: 'cartoon' })
                                .color({ custom: { molstar_use_default_coloring: true } })
                                .opacity({ opacity: opacity_val });
                        } else {
                            structure
                                .component({ selector: { auth_asym_id: name } })
                                .representation({ type: 'ball_and_stick' })
                                .color({ custom: { molstar_use_default_coloring: true } })
                                .opacity({ opacity: opacity_val });
                        }
                    }
                }

                const mvsData = builder.getState();

                await PluginExtensions.mvs.loadMVS(viewer.plugin, mvsData, {
                    sourceUrl: undefined,
                    sanityChecks: true,
                    replaceExisting: true,
                    keepCamera: segment === "SYSTEM",
                } as any);
            } catch (e) {
                console.error("Mol* viewer error", e);
            } finally {
                setLoading(false);
            }
        };

        // Debounce when segment changes
        if (segmentChanged) {
            debounceTimerRef.current = setTimeout(() => {
                render();
            }, 150);
        } else {
            // No debounce for initial render or other changes
            render();
        }

        return () => {
            if (debounceTimerRef.current) {
                clearTimeout(debounceTimerRef.current);
            }
        };
    }, [runId, segment, segments, renderData, structureError]);

    return (
        <Box sx={{ position: "relative", width: "100%", height: "100%" }}>
            {structureError && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                    {structureError}
                </Alert>
            )}
            {!structureError && (
                <div
                    ref={viewerContainerRef}
                    style={{
                        width: typeof width === 'number' ? `${width}px` : width,
                        height: typeof height === 'number' ? `${height}px` : height,
                        borderRadius: "8px",
                        overflow: "hidden",
                        position: "relative",
                    }}
                />
            )}
            {loading && (
                <Box
                    sx={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)" }}
                >
                    <CircularProgress />
                </Box>
            )}
        </Box>
    );
};

export default MDViewer;
