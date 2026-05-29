import { useEffect, useRef, useState } from "react";
import { Box, Typography, CircularProgress } from "@mui/material";

interface RenderPathsResponse {
    run_id: string;
    system_mmcif?: string | null;
    segments?: Record<string, string>;
}

const MOLSTAR_URL = "https://cdn.jsdelivr.net/npm/molstar";
const MOLSTAR_VERSION = "4.18.0";

interface MDViewerProps {
    runId: string;
    segment: string;
    segments: string[];
    width?: number | string;
    height?: number | string;
}

interface SegmentData {
    name: string;
    isProtein: boolean;
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
    const [molstarReady, setMolstarReady] = useState(false);
    const [renderData, setRenderData] = useState<RenderPathsResponse | null>(null);
    
    
    // Debounce refs
    const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const prevSegmentRef = useRef<string>(segment);

    useEffect(() => {
        const loadMolstar = async () => {
            if ((window as any).molstar) {
                setMolstarReady(true);
                return;
            }
            try {
                const script = document.createElement("script");
                script.src = `${MOLSTAR_URL}@${MOLSTAR_VERSION}/build/viewer/molstar.js`;
                script.async = true;

                const link = document.createElement("link");
                link.rel = "stylesheet";
                link.href = `${MOLSTAR_URL}@${MOLSTAR_VERSION}/build/viewer/molstar.css`;

                await Promise.all([
                    new Promise((res, rej) => {
                        script.onload = res;
                        script.onerror = rej;
                        document.head.appendChild(script);
                    }),
                    new Promise((res, rej) => {
                        link.onload = res;
                        link.onerror = rej;
                        document.head.appendChild(link);
                    }),
                ]);
                setMolstarReady(true);
            } catch (err) {
                console.error("Failed to load Mol*", err);
            }
        };
        loadMolstar();
    }, []);

    // Fetch render paths when molstar is ready
    useEffect(() => {
        if (!molstarReady || !runId) return;
        const fetchRenderPaths = async () => {
            try {
                const res = await fetch(`/runs/${runId}/render`);
                if (res.ok) {
                    const data: RenderPathsResponse = await res.json();
                    setRenderData(data);
                }
            } catch (e) {
                console.error("Failed to fetch render paths", e);
            }
        };
        fetchRenderPaths();
    }, [molstarReady, runId]);

    useEffect(() => {
        // Cleanup previous debounce timer
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
        }

        // Only debounce when segment changes (not on initial load or other deps change)
        const segmentChanged = prevSegmentRef.current !== segment;
        prevSegmentRef.current = segment;

        const render = async () => {
            if (!molstarReady || !viewerContainerRef.current) return;
            setLoading(true);
            viewerContainerRef.current.innerHTML = "";

            const molstar = (window as any).molstar;

            try {
                const viewer = await molstar.Viewer.create(viewerContainerRef.current, {
                    layoutIsExpanded: false,
                    layoutShowControls: false,
                });

                const builder = molstar.PluginExtensions.mvs.MVSData.createBuilder();

                // Use dynamic render path from API, fallback to hardcoded path
                const systemPath = renderData?.system_mmcif || "render/system.cif";
                const structureUrl = `/files/${runId}/${systemPath}`;

                const structure = builder
                    .download({ url: structureUrl })
                    .parse({ format: "mmcif" })
                    .modelStructure({});

                const safeSegments = Array.isArray(segments) ? segments : [];

                // Fetch segment type info
                const segmentData: SegmentData[] = await Promise.all(
                    safeSegments.map(async (seg) => {
                        let isProtein = false;
                        try {
                            const res = await fetch(`/runs/${runId}/verification?segment=${seg}`);
                            if (res.ok) {
                                const data = await res.json();
                                // Check if any hit is a protein type
                                isProtein = data.hits?.some((h: any) => 
                                    h.ident_type?.toLowerCase().includes('protein') ||
                                    h.ident_type?.toLowerCase().includes('uniprot')
                                ) || false;
                            }
                        } catch (e) {
                            console.error(`Failed to fetch type for ${seg}`, e);
                        }

                        return {
                            name: seg,
                            isProtein,
                        };
                    })
                );

                if (segment === "SYSTEM") {
                    // Show all segments at opacity 1.0 with default coloring
                    structure
                        .component({ selector: 'all' })
                        .representation({ type: 'cartoon' })
                        .color({ custom: { molstar_use_default_coloring: true } })
                        .opacity({ opacity: 1.0 });
                } else {
                    // Highlight/dim mode: background all segments at 0.15, foreground selected at 1.0
                    const selectedSegData = segmentData.find(sd => sd.name === segment);
                    const isProtein = selectedSegData?.isProtein ?? false;

                    // Background layer: ALL segments at opacity 0.15
                    structure
                        .component({ selector: 'all' })
                        .representation({ type: 'cartoon' })
                        .color({ custom: { molstar_use_default_coloring: true } })
                        .opacity({ opacity: 0.15 });

                    // Foreground layer: selected segment at opacity 1.0 with focus
                    structure
                        .component({ selector: { auth_asym_id: segment } })
                        .representation({ type: isProtein ? 'cartoon' : 'ball_and_stick' })
                        .color({ color: '#E65100' })
                        .opacity({ opacity: 1.0 })
                        .focus({});
                }

                const mvsData = builder.getState();

                await molstar.PluginExtensions.mvs.loadMVS(viewer.plugin, mvsData, {
                    sourceUrl: undefined,
                    sanityChecks: true,
                                    keepCamera: segment === "SYSTEM",
                });
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
    }, [runId, segment, segments, molstarReady]);

    return (
        <Box sx={{ m: 2, position: "relative", width: "100%", height: "100%" }}>
            <Typography variant="h2" sx={{ mb: 2 }}>
                Simulation Viewer
            </Typography>
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
