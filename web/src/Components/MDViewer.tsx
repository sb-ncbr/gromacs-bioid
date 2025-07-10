import { useEffect, useRef, useState } from "react";
import { Box, Typography, CircularProgress } from "@mui/material";

const MOLSTAR_URL = "https://cdn.jsdelivr.net/npm/molstar";
const MOLSTAR_VERSION = "4.18.0";

interface MDViewerProps {
    session: string;
    segment: string; // chain auth ID or 'SIMULATION'
    segments: string[]; // list of all chain auth IDs
    width?: number;
    height?: number;
}

const MDViewer = ({
                      session,
                      segment,
                      segments,
                      width = 600,
                      height = 400,
                  }: MDViewerProps) => {

    const viewerContainerRef = useRef<HTMLDivElement | null>(null);
    const [loading, setLoading] = useState(false);
    const [molstarReady, setMolstarReady] = useState(false);

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

    useEffect(() => {
        const render = async () => {
            if (!molstarReady || !viewerContainerRef.current) return;
            setLoading(true);
            viewerContainerRef.current.innerHTML = "";

            // const index = segments.indexOf("SIMULATION");
            // if (index > -1) {
            //     segments.splice(index, 1);
            // }

            const molstar = (window as any).molstar;

            try {
                const viewer = await molstar.Viewer.create(viewerContainerRef.current, {
                    layoutIsExpanded: false,
                    layoutShowControls: false,
                });

                const builder = molstar.PluginExtensions.mvs.MVSData.createBuilder();

                const structureUrl = `/api/annotate/${session}/results/system/system`;

                const structure = builder
                    .download({ url: structureUrl })
                    .parse({ format: "mmcif" })
                    .modelStructure({});


                const segmentData = await Promise.all(
                    segments.map(async (seg) => {

                        let isProtein = false;
                        try {
                            const res = await fetch(`/api/annotate/${session}/results/segment/${seg}/type`);
                            const type = await res.text();
                            console.log(type);
                            isProtein = (type.trim().toLowerCase() === "\"protein\"");
                        } catch (e) {
                            console.error(`Failed to fetch type for ${seg}`, e);
                        }

                        const opacity_val = segment === "system" || segment === seg ? 1.0 : 0.05;

                        return {
                            name: seg,
                            isProtein,
                            opacity_val
                        };
                    })
                );

                for (const { name, isProtein, opacity_val } of segmentData) {
                    console.log(`Segment: ${name} (${segment}), isProtein: ${isProtein}, opacity: ${opacity_val}`);

                    if (isProtein) {
                        structure
                            .component({selector: {auth_asym_id: name}})
                            .representation({ type: 'cartoon'})
                            .color({ custom: { molstar_use_default_coloring: true } })
                            .opacity({ opacity: opacity_val });
                    } else {
                        structure
                            .component({selector: {auth_asym_id: name}})
                            .representation({ type: 'ball_and_stick'})
                            .color({ custom: { molstar_use_default_coloring: true } })
                            .opacity({ opacity: opacity_val });
                    }
                }

                const mvsData = builder.getState();

                await molstar.PluginExtensions.mvs.loadMVS(viewer.plugin, mvsData, {
                    sourceUrl: undefined,
                    sanityChecks: true,
                    replaceExisting: true,
                });
            } catch (e) {
                console.error("Mol* viewer error", e);
            } finally {
                setLoading(false);
            }
        };

        render();
    }, [session, segment, segments, molstarReady]);

    return (
        <Box sx={{ m: 2, position: "relative" }}>
            <Typography variant="h2" sx={{ mb: 2 }}>
                Simulation Viewer
            </Typography>
            <div
                ref={viewerContainerRef}
                style={{
                    width,
                    height,
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