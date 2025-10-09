import { FC, useEffect, useState } from "react";
import {
    Box,
    Typography,
    Divider,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Button,
    CircularProgress,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DownloadIcon from "@mui/icons-material/Download";
import SegmentSelector from "../MDComponents/SegmentSelector";

interface Props {
    uuid: string;
}

interface Signature {
    id: string;
    name: string;
    description: string;
    short: string;
    full: string;
    filename: string;
}

const ShowSignatures: FC<Props> = ({ uuid }) => {
    const [activeSegment, setActiveSegment] = useState<string | null>(null);
    const [segmentName, setSegmentName] = useState<string | null>(null);
    const [signatures, setSignatures] = useState<Signature[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!activeSegment) return;

        const debugFetchJson = async (url: string) => {
            console.log("Fetching:", url);
            const res = await fetch(url);

            const text = await res.text();
            try {
                const json = JSON.parse(text);
                return json;
            } catch (err) {
                console.error("Failed to parse JSON from", url);
                console.error("Response was:", text);
                throw err;
            }
        };

        const fetchSignatures = async () => {
            setLoading(true);
            try {
                // Step 1: Get signature IDs
                const idsJson = await debugFetchJson(
                    `/api/annotate/${uuid}/results/signatures/${activeSegment}`
                );
                const ids: string[] = idsJson.result;


                // Step 2: Fetch details for each signature
                const details: Signature[] = await Promise.all(
                    ids.map(async (id) => {
                        const [name, description, short, full, filename] = await Promise.all([
                            debugFetchJson(`/api/annotate/${uuid}/results/signatureinfo/${activeSegment}/${id}/name`),
                            debugFetchJson(`/api/annotate/${uuid}/results/signatureinfo/${activeSegment}/${id}/description`),
                            debugFetchJson(`/api/annotate/${uuid}/results/signatureinfo/${activeSegment}/${id}/short`),
                            debugFetchJson(`/api/annotate/${uuid}/results/signatureinfo/${activeSegment}/${id}/full`),
                            debugFetchJson(`/api/annotate/${uuid}/results/signatureinfo/${activeSegment}/${id}/filename`),
                        ]);

                        return {
                            id,
                            name: name.result,
                            description: description.result,
                            short: short.result,
                            full: full.result,
                            filename: filename.result,
                        };
                    })
                );

                setSignatures(details);
            } catch (err) {
                console.error("Error fetching signatures:", err);
                setSignatures([]);
            } finally {
                setLoading(false);
            }
        };

        fetchSignatures();
    }, [uuid, activeSegment]);

    const handleDownload = (signature: Signature) => {
        const blob = new Blob([signature.full], { type: "text/plain" });
        const link = document.createElement("a");
        link.href = window.URL.createObjectURL(blob);
        link.download = signature.filename;
        link.click();
    };

    return (
        <Box sx={{ display: "flex", flexDirection: "column", height: "100%", width: "100%" }}>
            {/* Page header */}
            <Box sx={{ mb: 2 }}>
                <Typography variant="h4" fontWeight="bold" gutterBottom>
                    Generated signatures
                </Typography>
                <Divider />
            </Box>

            <Box sx={{ display: "flex", height: "100%" }}>
                {/* Left: segment selector */}
                <Box sx={{ flex: 2, pr: 2 }}>
                    <SegmentSelector
                        uuid={uuid}
                        onSelect={(segid, name) => {
                            setActiveSegment(segid);
                            setSegmentName(name);
                        }}
                    />
                </Box>

                {/* Right: signatures list */}
                <Box sx={{ flex: 3, p: 2, overflowY: "auto" }}>
                    {activeSegment ? (
                        <>
                            <Typography variant="h2" gutterBottom>
                                {segmentName} ({activeSegment})
                            </Typography>

                            {loading ? (
                                <CircularProgress />
                            ) : signatures.length === 0 ? (
                                <Typography color="text.secondary">No signatures found for this segment.</Typography>
                            ) : (
                                signatures.map((sig) => (
                                    <Accordion key={sig.id} sx={{ mb: 1 }}>
                                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                            <Typography variant="h6" fontWeight="bold">
                                                {sig.name}
                                            </Typography>
                                        </AccordionSummary>
                                        <AccordionDetails>
                                            <Typography variant="body2" color="text.secondary" gutterBottom>
                                                {sig.description}
                                            </Typography>
                                            <Typography
                                                variant="body2"
                                                sx={{
                                                    fontFamily: "monospace",
                                                    backgroundColor: "grey.100",
                                                    p: 1,
                                                    borderRadius: 1,
                                                    whiteSpace: "pre-wrap",
                                                }}
                                                gutterBottom
                                            >
                                                {sig.short}
                                            </Typography>
                                            <Button
                                                variant="contained"
                                                size="small"
                                                startIcon={<DownloadIcon />}
                                                onClick={() => handleDownload(sig)}
                                            >
                                                Download
                                            </Button>
                                        </AccordionDetails>
                                    </Accordion>
                                ))
                            )}
                        </>
                    ) : (
                        <Typography color="text.secondary">Select a segment to see signatures.</Typography>
                    )}
                </Box>
            </Box>
        </Box>
    );
};

export default ShowSignatures;
