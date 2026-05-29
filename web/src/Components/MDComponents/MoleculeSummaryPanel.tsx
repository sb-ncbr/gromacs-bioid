import React, { useEffect, useState } from "react";
import {
    Box,
    Typography,
    LinearProgress,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Stack,
    CircularProgress,
} from "@mui/material";

interface MoleculeSummaryPanelProps {
    uuid: string;
    segment: string;
}

interface MoleculeInfo {
    name: string;
    type: string;
    crossref_url?: string;
    confidence?: number;
}

interface SignatureSet {
    [key: string]: string | null;
}

interface IdentifierEntry {
    name?: string;
    identifier?: string;
    confidence?: number;
    observed_confidence?: number;
    crossref_count?: number;
    verification_method?: string;
}

const MoleculeSummaryPanel: React.FC<MoleculeSummaryPanelProps> = ({ uuid, segment }) => {
    const [info, setInfo] = useState<MoleculeInfo | null>(null);
    const [signatures, setSignatures] = useState<SignatureSet>({});
    const [identifiers, setIdentifiers] = useState<IdentifierEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [overlayOpen, setOverlayOpen] = useState(false);
    const [overlayContent, setOverlayContent] = useState<{ title: string; text: string }>({
        title: "",
        text: "",
    });

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);

                // Fetch molecule info
                const infoRes = await fetch(`/api/annotate/${uuid}/results/verification/${segment}/info`);
                if (infoRes.ok) {
                    setInfo(await infoRes.json());
                } else setInfo({ name: "Searching...", type: "unknown" });

                // Fetch signatures
                const sigRes = await fetch(`/api/annotate/${uuid}/results/verification/${segment}/signatures`);
                if (sigRes.ok) setSignatures(await sigRes.json());
                else setSignatures({});

                // Fetch identifiers
                const idRes = await fetch(`/api/annotate/${uuid}/results/verification/${segment}/identifiers`);
                if (idRes.ok) setIdentifiers(await idRes.json());
                else setIdentifiers([]);

            } catch (err) {
                setError("Failed to load molecule data.");
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [uuid, segment]);

    const openOverlay = (title: string, text: string) => {
        setOverlayContent({ title, text });
        setOverlayOpen(true);
    };

    const closeOverlay = () => setOverlayOpen(false);

    const confidence = info?.confidence ?? 0;
    const confidenceDisplay = Math.round(confidence);

    const signatureLabels: Record<string, string> = {
        atom: "Atom",
        fasta_protein: "FASTA Protein",
        fasta_nucleic: "FASTA Nucleic",
        pdb_protein: "PDB Protein",
        pdb_nucleic: "PDB Nucleic",
        smiles: "SMILES",
        name: "Name",
        fingerprint: "Fingerprint",
    };

    if (loading)
        return (
            <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%" }}>
                <CircularProgress />
            </Box>
        );

    if (error)
        return (
            <Typography color="error" variant="body2">
                {error}
            </Typography>
        );

    return (
        <Stack spacing={2} sx={{ height: "100%" }}>
            {/* Title */}
            <Typography variant="h5" sx={{ fontWeight: "bold" }}>
                {info?.name || "Searching..."}
            </Typography>

            {/* Type and link */}
            <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="body2" color="text.secondary">
                    {info?.type || ""}
                </Typography>
                {info?.crossref_url && (
                    <Button
                        size="small"
                        variant="text"
                        color="primary"
                        href={info.crossref_url}
                        target="_blank"
                        sx={{ textTransform: "none" }}
                    >
                        Crossref ↗
                    </Button>
                )}
            </Stack>

            {/* Confidence bar */}
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box sx={{ flexGrow: 1 }}>
                    <LinearProgress
                        variant="determinate"
                        value={confidence}
                        sx={{ height: 8, borderRadius: 5, backgroundColor: "#e0e0e0" }}
                    />
                </Box>
                <Typography variant="body2" sx={{ width: 40, textAlign: "right" }}>
                    {confidenceDisplay}%
                </Typography>
            </Box>

            {/* Signatures */}
            <Typography variant="h6" sx={{ mt: 1 }}>
                Signatures
            </Typography>
            <Stack direction="row" flexWrap="wrap" gap={1}>
                {Object.entries(signatureLabels).map(([key, label]) => {
                    const available = Boolean(signatures[key]);
                    return (
                        <Button
                            key={key}
                            variant="contained"
                            color={available ? "primary" : "inherit"}
                            disabled={!available}
                            onClick={() =>
                                available && openOverlay(label, signatures[key] || "")
                            }
                            sx={{
                                textTransform: "none",
                                minWidth: 130,
                                fontWeight: 600,
                                opacity: available ? 1 : 0.4,
                            }}
                        >
                            {label}
                        </Button>
                    );
                })}
            </Stack>

            {/* Identifiers Table */}
            <Typography variant="h6" sx={{ mt: 2 }}>
                Identifiers
            </Typography>
            {identifiers.length > 0 ? (
                <TableContainer component={Paper} sx={{ maxHeight: 300 }}>
                    <Table size="small" stickyHeader>
                        <TableHead>
                            <TableRow>
                                <TableCell>Name</TableCell>
                                <TableCell>Identifier</TableCell>
                                <TableCell>Conf.</TableCell>
                                <TableCell>Obs. Conf.</TableCell>
                                <TableCell>Crossrefs</TableCell>
                                <TableCell>Verification</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {identifiers.map((id, idx) => (
                                <TableRow key={idx}>
                                    <TableCell>{id.name || "-"}</TableCell>
                                    <TableCell>{id.identifier || "-"}</TableCell>
                                    <TableCell>{id.confidence ?? "-"}</TableCell>
                                    <TableCell>{id.observed_confidence ?? "-"}</TableCell>
                                    <TableCell>{id.crossref_count ?? "-"}</TableCell>
                                    <TableCell>{id.verification_method || "-"}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            ) : (
                <Typography variant="body2" color="text.secondary">
                    No identifiers found.
                </Typography>
            )}

            {/* Overlay */}
            <Dialog open={overlayOpen} onClose={closeOverlay} fullWidth maxWidth="md">
                <DialogTitle>{overlayContent.title}</DialogTitle>
                <DialogContent>
                    <TextField
                        value={overlayContent.text}
                        fullWidth
                        multiline
                        minRows={6}
                        variant="outlined"
                        InputProps={{ readOnly: true }}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={closeOverlay}>Close</Button>
                </DialogActions>
            </Dialog>
        </Stack>
    );
};

export default MoleculeSummaryPanel;
