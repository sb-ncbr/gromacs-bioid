import { useEffect, useRef, useState } from "react";
import { Box, Typography, CircularProgress } from "@mui/material"

const MOLSTAR_URL = "https://cdn.jsdelivr.net/npm/molstar";
const MOLSTAR_VERSION = "4.4.1";

interface ProteinViewerProps {
    pdbData: string | null
    uniprotId: string | null
    width?: number
    height?: number
}

const ProteinViewer = (props: ProteinViewerProps) => {
    const { pdbData, uniprotId, width, height } = props
    const viewerRef = useRef<HTMLDivElement | null>(null)
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!pdbData && !uniprotId) return;
        setLoading(true);

        const loadMolstar = async () => {
            try {
                const script = document.createElement("script");
                script.src = `${MOLSTAR_URL}@${MOLSTAR_VERSION}/build/viewer/molstar.js`;
                await new Promise((resolve, reject) => {
                    script.onload = resolve;
                    script.onerror = reject;
                    document.head.appendChild(script);
                });

                const link = document.createElement("link");
                link.rel = "stylesheet";
                link.href = `${MOLSTAR_URL}@${MOLSTAR_VERSION}/build/viewer/molstar.css`;
                await new Promise((resolve, reject) => {
                    link.onload = resolve;
                    link.onerror = reject;
                    document.head.appendChild(link);
                });

                if (!viewerRef.current) {
                    console.error("Viewer ref is null");
                    return;
                }

                const viewer = await window.molstar.Viewer.create(viewerRef.current, { layoutIsExpanded: false, layoutShowControls: false });
                if (pdbData) {
                    await viewer.loadStructureFromData(pdbData, 'pdb');
                } else {
                    await viewer.loadAlphaFoldDb(uniprotId!);
                }
            } catch (error) {
                console.error("Failed to initialize viewer:", error);
            } finally {
                setLoading(false);
            }
        };

        loadMolstar();
    }, [pdbData, uniprotId]);

    // don't render if there is no PDB
    if (!pdbData && !uniprotId) {
        return null;
    }

    return (
        <Box sx={{m: 3}}>
            <Typography variant="h1" sx={{ mb: 3 }}>
                {
                    pdbData ? "Simulation Preview" : "Protein Structure"
                }
            </Typography>
            <div style={{width: width, height: height, position: "relative", display: "flex", justifyContent: "center", alignItems: "center"}}>
                <div ref={viewerRef} />
                {
                    loading ? <CircularProgress /> : null
                }
            </div>
        </Box>
    );
}

export default ProteinViewer
