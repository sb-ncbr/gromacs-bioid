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
    Tabs,
    Tab,
} from "@mui/material";

interface MoleculeSummaryPanelProps {
    runId: string;
    segment: string;
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
    ident_type?: string;
    database?: string;
    final_confidence?: number;
    is_verified?: boolean;
}

interface SystemSummary {
    total_segments: number;
    total_fragment_count: number;
    type_counts: Record<string, number>;
}

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => {
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`molecule-tabpanel-${index}`}
            aria-labelledby={`molecule-tab-${index}`}
            {...other}
        >
            {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
        </div>
    );
};

const MoleculeSummaryPanel: React.FC<MoleculeSummaryPanelProps> = ({ runId, segment }) => {
    const [signatures, setSignatures] = useState<SignatureSet>({});
    const [identifiers, setIdentifiers] = useState<IdentifierEntry[]>([]);
    const [verification, setVerification] = useState<IdentifierEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [moleculeName, setMoleculeName] = useState<string>("Searching...");
    const [moleculeType, setMoleculeType] = useState<string>("unknown");
    const [confidence, setConfidence] = useState<number>(0);
    const [systemSummary, setSystemSummary] = useState<SystemSummary | null>(null);

    const [overlayOpen, setOverlayOpen] = useState(false);
    const [overlayContent, setOverlayContent] = useState<{ title: string; text: string }>({
        title: "",
        text: "",
    });

    const [tabValue, setTabValue] = useState(0);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                setError(null);

                // If SYSTEM, fetch summary data
                if (segment === "SYSTEM") {
                    const molRes = await fetch(`/runs/${runId}/molecules`);
                    if (molRes.ok) {
                        const molData = await molRes.json();
                        setSystemSummary({
                            total_segments: molData.segments?.length || 0,
                            total_fragment_count: molData.total_fragment_count || 0,
                            type_counts: molData.type_counts || {},
                        });
                    }
                    setMoleculeName("Whole System");
                    setMoleculeType("System overview");
                    setConfidence(0);
                    setSignatures({});
                    setIdentifiers([]);
                    setVerification([]);
                } else {
                    setSystemSummary(null);

                    // Fetch signatures
                    const sigRes = await fetch(`/runs/${runId}/signatures?segment=${segment}`);
                    if (sigRes.ok) {
                        const sigData = await sigRes.json();
                        const sigs: SignatureSet = {};
                        sigData.signatures?.forEach((sig: any) => {
                            sigs[sig.generator] = sig.signature;
                        });
                        setSignatures(sigs);
                        
                        // Use first signature as name if available
                        if (sigs.name) {
                            setMoleculeName(sigs.name as string);
                        } else if (Object.keys(sigs).length > 0) {
                            setMoleculeName(Object.keys(sigs)[0]);
                        }
                    } else {
                        setSignatures({});
                    }

                    // Fetch identifiers
                    const idRes = await fetch(`/runs/${runId}/identifiers?segment=${segment}`);
                    if (idRes.ok) {
                        const idData = await idRes.json();
                        const idents: IdentifierEntry[] = idData.hits?.map((hit: any) => ({
                            name: hit.ident_type,
                            identifier: hit.identifier,
                            confidence: hit.score ? hit.score * 100 : undefined,
                            crossref_count: 1,
                            verification_method: hit.hit_type,
                        })) || [];
                        setIdentifiers(idents);
                        
                        if (idents.length > 0) {
                            setMoleculeType(idents[0].name || "unknown");
                        }
                    } else {
                        setIdentifiers([]);
                    }

                    // Fetch verification
                    const verRes = await fetch(`/runs/${runId}/verification?segment=${segment}`);
                    if (verRes.ok) {
                        const verData = await verRes.json();
                        const verif: IdentifierEntry[] = verData.hits?.map((hit: any) => ({
                            name: hit.ident_type,
                            identifier: hit.identifier,
                            confidence: hit.final_confidence ? hit.final_confidence * 100 : undefined,
                            database: hit.database,
                            is_verified: hit.is_verified,
                            verification_method: hit.rejection_reason || "verified",
                        })) || [];
                        setVerification(verif);
                        
                        if (verif.length > 0) {
                            setConfidence(verif[0].confidence || 0);
                            if (verif[0].database) {
                                setMoleculeType(verif[0].database);
                            }
                        }
                    } else {
                        setVerification([]);
                    }
                }

            } catch (err) {
                setError("Failed to load molecule data.");
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
        // Reset to Summary tab when segment changes
        setTabValue(0);
    }, [runId, segment]);

    const openOverlay = (title: string, text: string) => {
        setOverlayContent({ title, text });
        setOverlayOpen(true);
    };

    const closeOverlay = () => setOverlayOpen(false);

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

    const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
        setTabValue(newValue);
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

    const displayData = verification.length > 0 ? verification : identifiers;

    return (
        <Stack spacing={0} sx={{ height: "100%" }}>
            {/* Tabs */}
            <Tabs value={segment === "SYSTEM" ? 0 : tabValue} onChange={handleTabChange} sx={{ borderBottom: 1, borderColor: "divider" }}>
                <Tab label="Summary" id="molecule-tab-0" aria-controls="molecule-tabpanel-0" />
                <Tab label="Signatures" id="molecule-tab-1" aria-controls="molecule-tabpanel-1" disabled={segment === "SYSTEM"} />
                <Tab label="Identifiers" id="molecule-tab-2" aria-controls="molecule-tabpanel-2" disabled={segment === "SYSTEM"} />
                <Tab label="Verification" id="molecule-tab-3" aria-controls="molecule-tabpanel-3" disabled={segment === "SYSTEM"} />
            </Tabs>

            {/* Tab Panels */}
            {/* Summary Tab */}
            <TabPanel value={segment === "SYSTEM" ? 0 : tabValue} index={0}>
                <Stack spacing={2}>
                    {segment === "SYSTEM" && systemSummary ? (
                        // System summary
                        <>
                            <Typography variant="h6" sx={{ fontWeight: "bold" }}>
                                {moleculeName}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Total Segments: {systemSummary.total_segments}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Total Fragments: {systemSummary.total_fragment_count}
                            </Typography>
                            {Object.entries(systemSummary.type_counts).length > 0 && (
                                <Box>
                                    <Typography variant="body2" sx={{ mb: 1 }}>
                                        Type Breakdown:
                                    </Typography>
                                    {Object.entries(systemSummary.type_counts).map(([type, count]) => (
                                        <Typography key={type} variant="body2" color="text.secondary" sx={{ ml: 2 }}>
                                            {type}: {count}
                                        </Typography>
                                    ))}
                                </Box>
                            )}
                        </>
                    ) : (
                        // Molecule summary
                        <>
                            <Typography variant="h5" sx={{ fontWeight: "bold" }}>
                                {moleculeName}
                            </Typography>

                            {/* Type and link */}
                            <Stack direction="row" spacing={1} alignItems="center">
                                <Typography variant="body2" color="text.secondary">
                                    {moleculeType}
                                </Typography>
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
                        </>
                    )}
                </Stack>
            </TabPanel>

            {/* Signatures Tab */}
            <TabPanel value={tabValue} index={1}>
                {segment === "SYSTEM" ? (
                    <Typography variant="body2" color="text.secondary">
                        Select a specific molecule to view signatures.
                    </Typography>
                ) : (
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
                )}
            </TabPanel>

            {/* Identifiers Tab */}
            <TabPanel value={tabValue} index={2}>
                {segment === "SYSTEM" ? (
                    <Typography variant="body2" color="text.secondary">
                        Select a specific molecule to view identifiers.
                    </Typography>
                ) : displayData.length > 0 ? (
                    <TableContainer component={Paper} sx={{ maxHeight: 300 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Name</TableCell>
                                    <TableCell>Identifier</TableCell>
                                    <TableCell>Conf.</TableCell>
                                    <TableCell>Database</TableCell>
                                    <TableCell>Verified</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {displayData.map((id, idx) => (
                                    <TableRow key={idx}>
                                        <TableCell>{id.name || "-"}</TableCell>
                                        <TableCell>{id.identifier || "-"}</TableCell>
                                        <TableCell>{id.confidence ? Math.round(id.confidence) + "%" : "-"}</TableCell>
                                        <TableCell>{id.database || "-"}</TableCell>
                                        <TableCell>{id.is_verified !== undefined ? (id.is_verified ? "Yes" : "No") : "-"}</TableCell>
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
            </TabPanel>

            {/* Verification Tab */}
            <TabPanel value={tabValue} index={3}>
                {segment === "SYSTEM" ? (
                    <Typography variant="body2" color="text.secondary">
                        Select a specific molecule to view verification.
                    </Typography>
                ) : displayData.length > 0 ? (
                    <TableContainer component={Paper} sx={{ maxHeight: 300 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Name</TableCell>
                                    <TableCell>Identifier</TableCell>
                                    <TableCell>Conf.</TableCell>
                                    <TableCell>Database</TableCell>
                                    <TableCell>Verified</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {displayData.map((id, idx) => (
                                    <TableRow key={idx}>
                                        <TableCell>{id.name || "-"}</TableCell>
                                        <TableCell>{id.identifier || "-"}</TableCell>
                                        <TableCell>{id.confidence ? Math.round(id.confidence) + "%" : "-"}</TableCell>
                                        <TableCell>{id.database || "-"}</TableCell>
                                        <TableCell>{id.is_verified !== undefined ? (id.is_verified ? "Yes" : "No") : "-"}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                ) : (
                    <Typography variant="body2" color="text.secondary">
                        No verification data found.
                    </Typography>
                )}
            </TabPanel>

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
