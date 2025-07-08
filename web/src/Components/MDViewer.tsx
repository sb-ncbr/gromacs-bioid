import { useEffect, useRef, useState } from "react";
import { Box, Typography, CircularProgress } from "@mui/material";

const MOLSTAR_URL = "https://cdn.jsdelivr.net/npm/molstar";
const MOLSTAR_VERSION = "4.4.1";

interface MDViewerProps {
    session: string;
    segment: string;
    width?: number;
    height?: number;
}

const MDViewer = ({ session, segment, width = 600, height = 400 }: MDViewerProps) => {
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
                    new Promise((resolve, reject) => {
                        script.onload = resolve;
                        script.onerror = reject;
                        document.head.appendChild(script);
                    }),
                    new Promise((resolve, reject) => {
                        link.onload = resolve;
                        link.onerror = reject;
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

            try {
                setLoading(true);

                // Remove any old viewer DOM
                viewerContainerRef.current.innerHTML = "";

                const response = await fetch(`/api/annotate/${session}/results/system/${segment}`);
                if (!response.ok) throw new Error("Failed to fetch structure");
                const cifText = await response.text();

                const viewer = await (window as any).molstar.Viewer.create(viewerContainerRef.current, {
                    layoutShowControls: false,
                    layoutIsExpanded: false,
                });

                await viewer.loadStructureFromData(cifText, "mmcif");
            } catch (error) {
                console.error("Mol* viewer error", error);
            } finally {
                setLoading(false);
            }
        };

        render();
    }, [session, segment, molstarReady]);

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
                    position: "relative"
                }}
            />
            {loading && (
                <Box sx={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)" }}>
                    <CircularProgress />
                </Box>
            )}
        </Box>
    );
};

export default MDViewer;
