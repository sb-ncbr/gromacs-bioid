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
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Stack,
    CircularProgress,
    Chip,
    Alert,
    Link,
    Tooltip,
} from "@mui/material";
import { fetchMoleculeName } from "../../utils/identifierNames";

// Helper function to determine file extension from generator name
const getSignatureExtension = (generator: string): string => {
    const gen = generator.toLowerCase();
    if (gen.includes('fasta')) return '.fasta';
    if (gen.includes('smiles')) return '.smi';
    if (gen.includes('pdb')) return '.pdb';
    if (gen.includes('mmcif')) return '.cif';
    if (gen.includes('atom') || gen.includes('formula') || gen.includes('fingerprint') || 
        gen.includes('name') || gen.includes('segment') || gen.includes('chain') || 
        gen.includes('molecule') || gen.includes('inchi') || gen.includes('morgan') || 
        gen.includes('selfies') || gen.includes('tdi') || gen.includes('glycan') || 
        gen.includes('lipid')) return '.txt';
    return '.txt';
};

// Helper function to download signature as file
const downloadSignature = (segment: string, generator: string, signature: string) => {
    const ext = getSignatureExtension(generator);
    const filename = `${segment}_${generator}${ext}`;
    const blob = new Blob([signature], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
};

interface MoleculeSummaryPanelProps {
    runId: string;
    segment: string;
    systemSummary?: {
        total_segments: number;
        total_fragment_count: number;
        type_counts: Record<string, number>;
    };
}

interface MoleculeInfo {
    segment: string;
    name: string;
    type: string;
    atom_count: number;
    residue_count: number;
    confidence: number;
}

interface VerificationHit {
    identifier: string;
    ident_type: string;
    database: string;
    resolver_score?: number | null;
    similarity_score?: number | null;
    annotation_quality_score?: number | null;
    final_confidence: number;
    is_verified: boolean;
    rejection_reason?: string | null;
    database_url?: string | null;
}

interface VerificationData {
    run_id: string;
    segment: string;
    hits: VerificationHit[];
}

interface Signature {
    segment: string;
    generator: string;
    signature: string;
}

interface SignaturesData {
    run_id: string;
    segment: string;
    signatures: Signature[];
    attempted_generators?: Record<string, boolean>;
}

interface IdentifierHit {
    identifier: string;
    ident_type: string;
    hit_type: string;
    resolver_name: string;
    score: number;
}

interface IdentifiersData {
    run_id: string;
    segment: string;
    hits: IdentifierHit[];
}

type DialogMode = 'off' | 'signatures' | 'identifiers' | 'verification';

const MoleculeSummaryPanel: React.FC<MoleculeSummaryPanelProps> = ({ runId, segment, systemSummary }) => {
    const [info, setInfo] = useState<MoleculeInfo | null>(null);
    const [verificationData, setVerificationData] = useState<VerificationData | null>(null);
    const [signaturesData, setSignaturesData] = useState<SignaturesData | null>(null);
    const [identifiersData, setIdentifiersData] = useState<IdentifiersData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [dialogMode, setDialogMode] = useState<DialogMode>('off');
    const [selectedSignature, setSelectedSignature] = useState<{ generator: string; signature: string } | null>(null);
    const [verificationNames, setVerificationNames] = useState<Record<string, string>>({});

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                setError(null);

                // If SYSTEM, use prop data (no fetch)
                if (segment === "SYSTEM") {
                    setInfo(null);
                    setVerificationData(null);
                    setSignaturesData(null);
                    setIdentifiersData(null);
                } else {
                    // Fetch molecule info
                    const infoRes = await fetch(`/runs/${runId}/molecules/${segment}/info`);
                    if (infoRes.ok) {
                        const infoData = await infoRes.json();
                        setInfo(infoData);
                    } else {
                        setInfo(null);
                    }

                    // Fetch verification
                    const verRes = await fetch(`/runs/${runId}/verification?segment=${segment}`);
                    if (verRes.ok) {
                        const verData = await verRes.json();
                        setVerificationData(verData);
                    } else {
                        setVerificationData(null);
                    }

                    // Fetch signatures
                    const sigRes = await fetch(`/runs/${runId}/signatures?segment=${segment}`);
                    if (sigRes.ok) {
                        const sigData = await sigRes.json();
                        setSignaturesData(sigData);
                    } else {
                        setSignaturesData(null);
                    }

                    // Fetch identifiers
                    const idRes = await fetch(`/runs/${runId}/identifiers?segment=${segment}`);
                    if (idRes.ok) {
                        const idData = await idRes.json();
                        setIdentifiersData(idData);
                    } else {
                        setIdentifiersData(null);
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
    }, [runId, segment]);

    useEffect(() => {
        if (dialogMode !== 'verification' || !verificationData?.hits?.length) return;
        let cancelled = false;
        const fetchAll = async () => {
            const map: Record<string, string> = {};
            await Promise.all(
                verificationData.hits.map(async (hit) => {
                    try {
                        const result = await fetchMoleculeName(hit.ident_type, hit.identifier);
                        if (!cancelled) map[`${hit.ident_type}:${hit.identifier}`] = result.name;
                    } catch {
                        if (!cancelled) map[`${hit.ident_type}:${hit.identifier}`] = hit.identifier;
                    }
                })
            );
            if (!cancelled) setVerificationNames(map);
        };
        fetchAll();
        return () => { cancelled = true; };
    }, [dialogMode, verificationData]);

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

    // System view
    if (segment === "SYSTEM") {
        return (
            <Stack spacing={2}>
                <Typography variant="h6" fontWeight="bold">Whole System</Typography>
                <Typography variant="body2" color="text.secondary">
                    Total Segments: {systemSummary?.total_segments ?? '-'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                    Total Fragments: {systemSummary?.total_fragment_count ?? '-'}
                </Typography>
                {Object.entries(systemSummary?.type_counts || {}).map(([type, count]) => (
                    <Typography key={type} variant="body2" color="text.secondary" sx={{ ml: 2 }}>
                        {type}: {count}
                    </Typography>
                ))}
            </Stack>
        );
    }

    // Segment view
    const topHits = verificationData?.hits
        ? [...verificationData.hits].sort((a, b) => b.final_confidence - a.final_confidence).slice(0, 5)
        : [];

    const rejectionReasons = verificationData?.hits
        ?.filter(h => h.rejection_reason)
        .map(h => h.rejection_reason!)
        .filter((reason, idx, arr) => arr.indexOf(reason) === idx) || [];

    return (
        <>
            <Stack spacing={2}>
                {/* Name */}
                <Typography variant="h6" fontWeight="bold">{info?.name || segment}</Typography>

                {/* Metadata row */}
                <Stack direction="row" spacing={1} flexWrap="wrap">
                    {info?.type && (
                        <Chip label={info.type} color="primary" size="small" />
                    )}
                    <Chip label={`Atoms: ${info?.atom_count ?? '-'}`} size="small" />
                    <Chip label={`Residues: ${info?.residue_count ?? '-'}`} size="small" />
                </Stack>

                {/* Confidence */}
                {info?.confidence !== undefined && info.confidence !== null && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LinearProgress
                            variant="determinate"
                            value={Math.min(info.confidence ?? 0, 100)}
                            sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
                        />
                        <Typography variant="body2">{Math.round(info.confidence ?? 0)}%</Typography>
                    </Box>
                )}

                {/* Top Identifiers */}
                <Typography variant="subtitle2">Top Identifiers</Typography>
                {topHits.length > 0 ? (
                    <Stack spacing={1}>
                        {topHits.map((hit, idx) => (
                            <Box
                                key={idx}
                                sx={{
                                    display: 'grid',
                                    gridTemplateColumns: '1fr auto auto',
                                    gap: 1,
                                    alignItems: 'center',
                                    py: 0.5,
                                    borderBottom: idx < topHits.length - 1 ? '1px solid' : 'none',
                                    borderColor: 'divider',
                                }}
                            >
                                <Typography variant="body2" fontFamily="monospace" sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {hit.identifier}
                                </Typography>
                                <Chip label={hit.database || hit.ident_type} size="small" color={hit.is_verified ? "success" : "default"} />
                                <Typography variant="caption" sx={{ minWidth: 32, textAlign: 'right' }}>
                                    {Math.min(Math.round(hit.final_confidence ?? 0), 100)}%
                                </Typography>
                            </Box>
                        ))}
                    </Stack>
                ) : (
                    <Typography variant="body2" color="text.secondary">No identifiers found.</Typography>
                )}

                {/* Action buttons */}
                <Stack direction="row" spacing={1} flexWrap="wrap">
                    <Button
                        variant="outlined"
                        size="small"
                        onClick={() => setDialogMode('signatures')}
                    >
                        View Signatures
                    </Button>
                    <Button
                        variant="outlined"
                        size="small"
                        onClick={() => setDialogMode('identifiers')}
                    >
                        View Identifiers
                    </Button>
                    <Button
                        variant="outlined"
                        size="small"
                        onClick={() => setDialogMode('verification')}
                    >
                        View Verification
                    </Button>
                </Stack>

                {/* Rejection reasons */}
                {rejectionReasons.length > 0 && (
                    <Alert severity="info" sx={{ fontSize: '0.75rem' }}>
                        <Typography variant="caption" fontWeight="bold">Rejection reasons:</Typography>
                        <ul style={{ margin: 0, paddingLeft: '1.2em' }}>
                            {rejectionReasons.map((reason, idx) => (
                                <li key={idx}>{reason}</li>
                            ))}
                        </ul>
                    </Alert>
                )}
            </Stack>

            {/* Signatures Dialog */}
            <Dialog open={dialogMode === 'signatures'} onClose={() => { setDialogMode('off'); setSelectedSignature(null); }} fullWidth maxWidth="md">
                <DialogTitle>Signatures</DialogTitle>
                <DialogContent>
                    <Stack spacing={2} sx={{ mt: 1 }}>
                        <Stack direction="row" flexWrap="wrap" gap={1}>
                            {signaturesData?.signatures?.map((sig, idx) => (
                                <Button
                                    key={idx}
                                    variant={selectedSignature?.generator === sig.generator ? "contained" : "outlined"}
                                    size="small"
                                    onClick={() => setSelectedSignature({ generator: sig.generator, signature: sig.signature })}
                                >
                                    {sig.generator}
                                </Button>
                            ))}
                            {!signaturesData?.signatures?.length && (
                                <Typography variant="body2" color="text.secondary">No signatures available.</Typography>
                            )}
                        </Stack>
                        {selectedSignature && (
                            <Paper variant="outlined" sx={{ p: 2, backgroundColor: '#f5f5f5' }}>
                                <Typography variant="caption" fontWeight="bold" display="block" gutterBottom>
                                    {selectedSignature.generator}
                                </Typography>
                                <Typography variant="body2" fontFamily="monospace" sx={{ wordBreak: 'break-all' }}>
                                    {selectedSignature.signature}
                                </Typography>
                            </Paper>
                        )}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button 
                        variant="outlined" 
                        onClick={() => {
                            if (selectedSignature) {
                                downloadSignature(segment, selectedSignature.generator, selectedSignature.signature);
                            }
                        }}
                        disabled={!selectedSignature}
                    >
                        Download
                    </Button>
                    <Button onClick={() => { setDialogMode('off'); setSelectedSignature(null); }}>Close</Button>
                </DialogActions>
            </Dialog>

            {/* Identifiers Dialog */}
            <Dialog open={dialogMode === 'identifiers'} onClose={() => setDialogMode('off')} fullWidth maxWidth="md">
                <DialogTitle>Identifiers</DialogTitle>
                <DialogContent>
                    <TableContainer component={Paper} sx={{ mt: 1, maxHeight: 400 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Segment</TableCell>
                                    <TableCell>Identifier</TableCell>
                                    <TableCell>Type</TableCell>
                                    <TableCell>Resolver</TableCell>
                                    <TableCell>Score</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {identifiersData?.hits?.map((hit, idx) => (
                                    <TableRow key={idx}>
                                        <TableCell>{hit.identifier ? segment : '-'}</TableCell>
                                        <TableCell>{hit.identifier || '-'}</TableCell>
                                        <TableCell>{hit.ident_type || '-'}</TableCell>
                                        <TableCell>{hit.resolver_name || '-'}</TableCell>
                                        <TableCell>{hit.score !== undefined && hit.score !== null ? Math.round(hit.score) + '%' : (hit.identifier ? 'Identity' : '-')}</TableCell>
                                    </TableRow>
                                ))}
                                {!identifiersData?.hits?.length && (
                                    <TableRow>
                                        <TableCell colSpan={5} align="center">No identifiers found.</TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogMode('off')}>Close</Button>
                </DialogActions>
            </Dialog>

            {/* Verification Dialog */}
            <Dialog open={dialogMode === 'verification'} onClose={() => setDialogMode('off')} fullWidth maxWidth="md">
                <DialogTitle>Verification</DialogTitle>
                <DialogContent>
                    <TableContainer component={Paper} sx={{ mt: 1, maxHeight: 500 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Name</TableCell>
                                    <TableCell>Identifier</TableCell>
                                    <TableCell>Type</TableCell>
                                    <TableCell>Database</TableCell>
                                    <TableCell>Resolver</TableCell>
                                    <TableCell>Similarity</TableCell>
                                    <TableCell>Annotation</TableCell>
                                    <TableCell>Confidence</TableCell>
                                    <TableCell>Verified</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {verificationData?.hits?.map((hit) => {
                                    const key = `${hit.ident_type}:${hit.identifier}`;
                                    const name = verificationNames[key] || hit.identifier;
                                    return (
                                        <TableRow key={key}>
                                            <TableCell>
                                                <Tooltip title={name}>
                                                    <Typography variant="body2" noWrap sx={{ maxWidth: 180 }}>
                                                        {name}
                                                    </Typography>
                                                </Tooltip>
                                            </TableCell>
                                            <TableCell>
                                                {hit.database_url ? (
                                                    <Link href={hit.database_url} target="_blank" rel="noopener noreferrer">
                                                        {hit.identifier}
                                                    </Link>
                                                ) : (
                                                    <Typography variant="body2">{hit.identifier}</Typography>
                                                )}
                                            </TableCell>
                                            <TableCell>{hit.ident_type || '—'}</TableCell>
                                            <TableCell>{hit.database || '—'}</TableCell>
                                            <TableCell>{hit.resolver_score != null ? Math.min(Math.round(hit.resolver_score), 100) + '%': '—'}</TableCell>
                                            <TableCell>{hit.similarity_score != null ? Math.round(hit.similarity_score) + '%' : '—'}</TableCell>
                                            <TableCell>{hit.annotation_quality_score != null ? Math.round(hit.annotation_quality_score) + '%' : '—'}</TableCell>
                                            <TableCell>{Math.min(Math.round(hit.final_confidence ?? 0), 100)}%</TableCell>
                                            <TableCell>
                                                {hit.is_verified ? (
                                                    <Chip label="Yes" color="success" size="small" />
                                                ) : (
                                                    <Chip label="No" color="error" size="small" />
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                                {!verificationData?.hits?.length && (
                                    <TableRow>
                                        <TableCell colSpan={9} align="center">No verification data found.</TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogMode('off')}>Close</Button>
                </DialogActions>
            </Dialog>
        </>
    );
};

export default MoleculeSummaryPanel;
