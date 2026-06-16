import { useEffect, useState, useRef, useCallback } from "react";
import {
    Alert, AlertTitle,
    Box,
    Grid,
    Stack,
    Typography,
    CircularProgress,
    
    Paper,
    IconButton,
    Tooltip,
    Tabs,
    Tab,
    Button,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
} from "@mui/material";
import { useParams } from "react-router-dom";
import TasksProgressBar, { TaskInfo } from "../Components/TasksProgressBar";
import SegmentSelector from "../Components/MDComponents/SegmentSelector";
import MDViewer from "../Components/MDComponents/MDViewer";
import MoleculeSummaryPanel from "../Components/MDComponents/MoleculeSummaryPanel";
import DownloadActions from "../Components/DownloadActions";
import LogViewer from "../Components/LogViewer";
import RunFileBrowser from "../Components/RunFileBrowser";
import { Article, OpenInNew } from "@mui/icons-material";

interface PipelineStatus {
    run_id: string;
    pipeline_name: string;
    status: string;
    started_at?: string | null;
    finished_at?: string | null;
    input_kind?: string | null;
    input_files?: Record<string, string>;
    metadata?: Record<string, any>;
}

interface WarningItem {
    code: string;
    message: string;
    step_id?: string | null;
    details?: Record<string, any>;
}

interface ErrorItem {
    code: string;
    message: string;
    step_id?: string | null;
    details?: Record<string, any>;
    critical?: boolean;
    exception_type?: string | null;
}

interface EventItem {
    kind: string;
    timestamp: string;
    level?: string | null;
    message?: string | null;
    task_id?: string | null;
}

interface RunStatusResponse {
    run_id: string;
    pipeline: PipelineStatus;
    tasks: TaskInfo[];
    warnings: WarningItem[];
    critical_errors: ErrorItem[];
    events: EventItem[];
}

interface LoadingAttemptInfo {
    strategy: string;
    success: boolean;
    error?: string | null;
}

interface LoadingInfoResponse {
    run_id: string;
    input_kind?: string | null;
    selected_strategy?: string | null;
    topology_files: string[];
    attempts: LoadingAttemptInfo[];
    final_strategy?: string | null;
    success: boolean;
    warnings: string[];
}

interface MoleculeSummaryResponse {
    run_id: string;
    segments: string[];
    unique_molecules?: Record<string, any>;
    type_counts?: Record<string, number>;
    total_fragment_count?: number;
    segment_meta?: Record<string, any>;
}

interface SignatureItem {
    segment: string;
    generator: string;
    signature?: string | null;
}

interface SignaturesResponse {
    run_id: string;
    signatures: SignatureItem[];
}

interface IdentifierHit {
    identifier: string;
    ident_type: string;
    hit_type: string;
    resolver_name: string;
    segment: string | null;
    score: number | null;
    database_url: string | null;
    evalue: number | null;
    bit_score: number | null;
    identity_percent: number | null;
    coverage_percent: number | null;
}

interface ResolverErrorItem {
    resolver_name: string;
    generator: string | null;
    message: string;
}

interface IdentifiersData {
    run_id: string;
    segment: string;
    hits: IdentifierHit[];
    attempted_resolvers: string[];
    failed_resolvers: ResolverErrorItem[];
}

type ActiveTab = 'overview' | 'loading' | 'warnings' | 'files' | 'signatures';

const RunResults = () => {
    const { runId } = useParams<{ runId: string }>();
    const [statusData, setStatusData] = useState<RunStatusResponse | null>(null);
    const [initialLoading, setInitialLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [segments, setSegments] = useState<string[]>([]);
    const [selectedSegment, setSelectedSegment] = useState<string>("SYSTEM");
    const [loadingInfo, setLoadingInfo] = useState<LoadingInfoResponse | null>(null);
    const [logOpen, setLogOpen] = useState(false);
    const [moleculeFetchError, setMoleculeFetchError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<ActiveTab>('overview');
    const [noCoordinates, setNoCoordinates] = useState(false);
    
    // Ref to track latest status for polling decisions
    const latestStatusRef = useRef<RunStatusResponse | null>(null);

    const [segmentMeta, setSegmentMeta] = useState<Record<string, any> | null>(null);
    const [signatures, setSignatures] = useState<SignaturesResponse | null>(null);
    const [totalFragmentCount, setTotalFragmentCount] = useState<number | undefined>(undefined);
    const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});
    
    // Identifiers state
    const [identifiersData, setIdentifiersData] = useState<IdentifiersData | null>(null);

    // Refs to track last-known values to prevent unnecessary re-renders
    const segmentsRef = useRef<string[]>([]);
    const segmentMetaRef = useRef<Record<string, any> | null>(null);
    const typeCountsRef = useRef<Record<string, number>>({});
    const totalFragmentCountRef = useRef<number | undefined>(undefined);

    const fetchMolecules = useCallback(async (id: string) => {
        try {
            const res = await fetch(`/runs/${id}/molecules`);
            if (res.ok) {
                const data: MoleculeSummaryResponse = await res.json();
                
                // Only update segments if changed
                const newSegments = data.segments || [];
                if (JSON.stringify(newSegments) !== JSON.stringify(segmentsRef.current)) {
                    setSegments(newSegments);
                    segmentsRef.current = newSegments;
                }
                
                // Only update segmentMeta if changed
                const newSegmentMeta = data.segment_meta || null;
                if (JSON.stringify(newSegmentMeta) !== JSON.stringify(segmentMetaRef.current)) {
                    setSegmentMeta(newSegmentMeta);
                    segmentMetaRef.current = newSegmentMeta;
                }
                
                // Only update totalFragmentCount if changed
                if (data.total_fragment_count !== totalFragmentCountRef.current) {
                    setTotalFragmentCount(data.total_fragment_count);
                    totalFragmentCountRef.current = data.total_fragment_count;
                }
                
                // Only update typeCounts if changed
                const newTypeCounts = data.type_counts || {};
                if (JSON.stringify(newTypeCounts) !== JSON.stringify(typeCountsRef.current)) {
                    setTypeCounts(newTypeCounts);
                    typeCountsRef.current = newTypeCounts;
                }
                
                // Default to SYSTEM instead of first segment
                setSelectedSegment("SYSTEM");
            } else {
                console.error("Failed to fetch molecules:", res.status);
                setMoleculeFetchError(`Failed to load molecule data (HTTP ${res.status}).`);
            }
        } catch (err) {
            console.error("Failed to fetch molecules:", err);
            setMoleculeFetchError("Failed to load molecule data.");
        }
    }, []);

    const fetchLoadingInfo = useCallback(async (id: string) => {
        try {
            const res = await fetch(`/runs/${id}/loading`);
            if (res.ok) {
                const data: LoadingInfoResponse = await res.json();
                setLoadingInfo(data);
                if (data.selected_strategy === "TPR_ONLY") {
                    setNoCoordinates(true);
                } else {
                    setNoCoordinates(false);
                }
            } else {
                console.error("Failed to fetch loading info:", res.status);
            }
        } catch (err) {
            console.error("Failed to fetch loading info:", err);
        }
    }, []);

    const fetchSignatures = useCallback(async (id: string) => {
        try {
            const res = await fetch(`/runs/${id}/signatures`);
            if (res.ok) {
                const data: SignaturesResponse = await res.json();
                setSignatures(data);
            } else {
                console.error("Failed to fetch signatures:", res.status);
            }
        } catch (err) {
            console.error("Failed to fetch signatures:", err);
        }
    }, []);

    const fetchIdentifiers = useCallback(async (id: string) => {
        try {
            const res = await fetch(`/runs/${id}/identifiers`);
            if (res.ok) {
                const data: IdentifiersData = await res.json();
                setIdentifiersData(data);
            } else {
                console.error("Failed to fetch identifiers:", res.status);
            }
        } catch (err) {
            console.error("Failed to fetch identifiers:", err);
        }
    }, []);

    // Poll for status
    useEffect(() => {
        if (!runId) return;

        let interval: ReturnType<typeof setInterval> | null = null;

        const fetchStatus = async () => {
            try {
                const response = await fetch(`/runs/${runId}/status`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                setStatusData(data);
                latestStatusRef.current = data;

                // Always fetch molecules and loading info when status succeeds
                fetchMolecules(data.run_id);
                fetchSignatures(data.run_id);
                fetchLoadingInfo(data.run_id);
                fetchIdentifiers(data.run_id);

                // Stop polling if success or failed
                if (data.pipeline.status === 'success' || data.pipeline.status === 'failed') {
                    if (interval) {
                        clearInterval(interval);
                        interval = null;
                    }
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to fetch status");
            } finally {
                if (initialLoading) {
                    setInitialLoading(false);
                }
            }
        };

        fetchStatus();

        interval = setInterval(() => {
            fetchStatus();
        }, 3000);

        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [runId, fetchMolecules, fetchLoadingInfo, fetchSignatures, fetchIdentifiers]);

    if (initialLoading) {
        return (
            <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "400px" }}>
                <CircularProgress />
            </Box>
        );
    }

    const isFailed = statusData?.pipeline.status === 'failed';

    const handleTabChange = (_event: React.SyntheticEvent, newValue: ActiveTab) => {
        setActiveTab(newValue);
    };

    // Helper to get display score for a hit
    const getHitScoreDisplay = (hit: IdentifierHit): string => {
        if (hit.hit_type === 'identity' || hit.score === null) {
            return 'Identity';
        }
        return `${Math.round(hit.score)}%`;
    };

    // Get top 5 hits sorted by score descending
    const getTopHits = (): IdentifierHit[] => {
        if (!identifiersData?.hits?.length) return [];
        return [...identifiersData.hits]
            .sort((a, b) => {
                const scoreA = a.hit_type === 'identity' || a.score === null ? 100 : a.score;
                const scoreB = b.hit_type === 'identity' || b.score === null ? 100 : b.score;
                return scoreB - scoreA;
            })
            .slice(0, 5);
    };

    return (
        <>
            <Stack spacing={3}>
                {/* Title */}
                <Typography variant="h1">Annotation process</Typography>

                {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                        <AlertTitle>Oh no — something went wrong!</AlertTitle>
                        {error}
                        <Typography variant="body2" sx={{ mt: 1 }}>
                            Don't worry — you can still inspect run files and logs below.
                        </Typography>
                    </Alert>
                )}

                {/* Progress bar with logs button */}
                {statusData && (
                    <>
                        <Box sx={{ display: "flex", alignItems: "center", width: "100%", overflowX: "auto", pb: 2 }}>
                            <TasksProgressBar 
                                tasks={statusData.tasks || []} 
                            />
                            <Tooltip title="View Logs">
                                <IconButton onClick={() => setLogOpen(true)} sx={{ ml: 2 }}>
                                    <Article />
                                </IconButton>
                            </Tooltip>
                        </Box>

                        {/* Low bond topology warning banner */}
                        {statusData?.warnings?.some(w => w.code === 'insufficient_bonds') && (
                            <Alert severity="warning" sx={{ mb: 2 }}>
                                <AlertTitle>Low bond topology detected</AlertTitle>
                                The input structure has very few chemical bonds defined. This usually happens with PDB files that lack CONECT records.{" "}
                                <strong>Enable "guess_missing_bonds" in the loader configuration</strong>{" "}
                                (Upload &rarr; Customize Config &rarr; Loader &rarr; Guess Missing Bonds) and re-run for proper molecule detection.
                            </Alert>
                        )}

                        {/* Failed banner */}
                        {isFailed && (
                            <Alert severity="error">
                                Annotation process failed. Check critical errors below.
                            </Alert>
                        )}

                        {/* Molecule fetch error warning */}
                        {moleculeFetchError && (
                            <Alert severity="warning" sx={{ mb: 2 }}>
                                {moleculeFetchError}
                            </Alert>
                        )}

                        {/* Results grid - combined viewer + selector panel */}
                        <Grid container spacing={2} sx={{ width: "100%", mt: 2 }}>
                            {/* Combined Viewer + Selector panel (8 columns) */}
                            <Grid item xs={12} md={8}>
                                <Box
                                    sx={{
                                        border: "1px solid",
                                        borderColor: "divider",
                                        borderRadius: 2,
                                        p: 2,
                                        height: "100%",
                                        display: "flex",
                                        flexDirection: "column",
                                    }}
                                >
                                    <SegmentSelector
                                        segments={segments}
                                        selectedSegment={selectedSegment}
                                        onSelect={setSelectedSegment}
                                        segmentMeta={segmentMeta || undefined}
                                    />
                                    <Box sx={{ flexGrow: 1, minHeight: 400, mt: 2 }}>
                                        {noCoordinates ? (
                                            <Alert severity="warning" sx={{ flexGrow: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                                                This run was loaded without structure coordinates (TPR-only). Molecular visualization is unavailable.
                                            </Alert>
                                        ) : (
                                            <MDViewer
                                                key={`${runId}-${selectedSegment}`}
                                                runId={runId!}
                                                segment={selectedSegment}
                                                segments={segments}
                                            />
                                        )}
                                    </Box>
                                </Box>
                            </Grid>

                            {/* Molecule Summary Panel (4 columns) */}
                            <Grid item xs={12} md={4}>
                                <Box
                                    sx={{
                                        border: "1px solid",
                                        borderColor: "divider",
                                        borderRadius: 2,
                                        p: 2,
                                        height: "100%",
                                    }}
                                >
                                    <MoleculeSummaryPanel
                                        runId={runId!}
                                        segment={selectedSegment}
                                        systemSummary={{
                                            total_segments: segments.length,
                                            total_fragment_count: totalFragmentCount ?? 0,
                                            type_counts: typeCounts,
                                        }}
                                    />
                                </Box>
                            </Grid>
                        </Grid>

                        {/* Global tabs below viewer grid */}
                        <Paper variant="outlined" sx={{ mt: 3 }}>
                            <Tabs value={activeTab} onChange={handleTabChange} sx={{ borderBottom: 1, borderColor: "divider" }}>
                                <Tab label="Overview" value="overview" />
                                <Tab label="Loading" value="loading" />
                                <Tab label="Warnings" value="warnings" />
                                <Tab label="Files" value="files" />
                                <Tab label="Signatures" value="signatures" />
                            </Tabs>

                            {/* Overview Tab */}
                            {activeTab === 'overview' && (
                                <Box sx={{ p: 3 }}>
                                    <Stack spacing={2}>
                                        {/* Topology-less search indicator */}
                                        {signatures && signatures.signatures && 
                                         signatures.signatures.some(s => s.generator === 'topology_less_pdb' || s.generator === 'ca_only_pdb') && (
                                            <Alert severity="info" sx={{ mb: 1 }}>
                                                This run used Quick Structure Search (topology-less).
                                            </Alert>
                                        )}
                                        <Typography variant="body2">Run ID: {statusData.run_id}</Typography>
                                        <Typography variant="body2">
                                            Status: <strong style={{ textTransform: 'capitalize' }}>{statusData.pipeline.status}</strong>
                                        </Typography>
                                        {statusData.pipeline.input_kind && (
                                            <Typography variant="body2">
                                                Input Kind: <strong>{statusData.pipeline.input_kind}</strong>
                                            </Typography>
                                        )}
                                        {statusData?.pipeline.input_files && (
                                            <Typography variant="body2">
                                                Input Files: <strong>{Object.keys(statusData?.pipeline.input_files || {}).join(", ")}</strong>
                                            </Typography>
                                        )}
                                        {statusData.pipeline.started_at && (
                                            <Typography variant="body2">
                                                Started: {new Date(statusData.pipeline.started_at).toLocaleString()}
                                            </Typography>
                                        )}
                                        {statusData.pipeline.finished_at && (
                                            <Typography variant="body2">
                                                Finished: {new Date(statusData.pipeline.finished_at).toLocaleString()}
                                            </Typography>
                                        )}

                                        {/* Top Identifiers Section */}
                                        {identifiersData?.hits && identifiersData.hits.length > 0 && (
                                            <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                                                <Typography variant="subtitle1" fontWeight="bold" sx={{ mb: 1 }}>Top Identifiers</Typography>
                                                <Stack spacing={1} sx={{ mb: 2 }}>
                                                    <Typography variant="body2">
                                                        Total hits: <strong>{identifiersData.hits.length}</strong>
                                                    </Typography>
                                                    <Typography variant="body2">
                                                        Resolvers attempted: <strong>{identifiersData.attempted_resolvers?.length || 0}</strong>
                                                        {identifiersData.failed_resolvers && identifiersData.failed_resolvers.length > 0 && (
                                                            <span> (<strong style={{ color: 'error.main' }}>Failed: {identifiersData.failed_resolvers.length}</strong>)</span>
                                                        )}
                                                    </Typography>
                                                </Stack>
                                                <TableContainer>
                                                    <Table size="small">
                                                        <TableHead>
                                                            <TableRow>
                                                                <TableCell>Segment</TableCell>
                                                                <TableCell>Identifier</TableCell>
                                                                <TableCell>Type</TableCell>
                                                                <TableCell>Resolver</TableCell>
                                                                <TableCell>Score</TableCell>
                                                                <TableCell>Links</TableCell>
                                                            </TableRow>
                                                        </TableHead>
                                                        <TableBody>
                                                            {getTopHits().map((hit, idx) => (
                                                                <TableRow key={idx} hover>
                                                                    <TableCell>{hit.segment}</TableCell>
                                                                    <TableCell>{hit.identifier}</TableCell>
                                                                    <TableCell>{hit.ident_type}</TableCell>
                                                                    <TableCell>{hit.resolver_name}</TableCell>
                                                                    <TableCell>{getHitScoreDisplay(hit)}</TableCell>
                                                                    <TableCell>
                                                                        {hit.database_url && (
                                                                            <Tooltip title="Open in database">
                                                                                <IconButton
                                                                                    size="small"
                                                                                    href={hit.database_url}
                                                                                    target="_blank"
                                                                                    rel="noopener noreferrer"
                                                                                >
                                                                                    <OpenInNew fontSize="small" />
                                                                                </IconButton>
                                                                            </Tooltip>
                                                                        )}
                                                                    </TableCell>
                                                                </TableRow>
                                                            ))}
                                                        </TableBody>
                                                    </Table>
                                                </TableContainer>
                                            </Paper>
                                        )}

                                        {/* Events */}
                                        {statusData.events && statusData.events.length > 0 && (
                                            <Box sx={{ mt: 2 }}>
                                                <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1 }}>Events</Typography>
                                                <Box sx={{ maxHeight: 200, overflow: 'auto', border: 1, borderColor: 'divider', borderRadius: 1, p: 1 }}>
                                                    {statusData.events.slice(-20).reverse().map((event, idx) => (
                                                        <Typography key={idx} variant="body2" sx={{ py: 0.5 }}>
                                                            <strong>[{event.kind}]</strong> {new Date(event.timestamp).toLocaleTimeString()} - {event.message || "No message"}
                                                        </Typography>
                                                    ))}
                                                </Box>
                                            </Box>
                                        )}

                                        {/* Download actions */}
                                        <Box sx={{ mt: 2 }}>
                                            <DownloadActions runId={runId!} />
                                        </Box>
                                    </Stack>
                                </Box>
                            )}

                            {/* Loading Tab */}
                            {activeTab === 'loading' && (
                                <Box sx={{ p: 3 }}>
                                    {loadingInfo ? (
                                        <Stack spacing={1}>
                                            <Typography variant="body2">
                                                <strong>Strategy:</strong> {loadingInfo.selected_strategy || loadingInfo.final_strategy || "N/A"}
                                            </Typography>
                                            <Typography variant="body2">
                                                <strong>Input Kind:</strong> {loadingInfo.input_kind || "N/A"}
                                            </Typography>
                                            <Typography variant="body2">
                                                <strong>Success:</strong> {loadingInfo.success ? "Yes" : "No"}
                                            </Typography>
                                            {loadingInfo.topology_files && loadingInfo.topology_files.length > 0 && (
                                                <Typography variant="body2">
                                                    <strong>Topology Files:</strong> {loadingInfo.topology_files.join(", ")}
                                                </Typography>
                                            )}
                                            {loadingInfo.attempts && loadingInfo.attempts.length > 0 && (
                                                <Typography variant="body2">
                                                    <strong>Attempts:</strong>
                                                    <ul>
                                                        {loadingInfo.attempts.map((attempt, idx) => (
                                                            <li key={idx}>
                                                                {attempt.strategy}: {attempt.success ? "Success" : `Failed - ${attempt.error}`}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </Typography>
                                            )}
                                        </Stack>
                                    ) : (
                                        <Typography variant="body2" color="text.secondary">No loading information available.</Typography>
                                    )}
                                </Box>
                            )}

                            {/* Warnings Tab */}
                            {activeTab === 'warnings' && (
                                <Box sx={{ p: 3 }}>
                                    {(!statusData?.warnings || statusData.warnings.length === 0) && 
                                     (!statusData?.critical_errors || statusData.critical_errors.length === 0) ? (
                                        <Alert severity="info">No warnings.</Alert>
                                    ) : (
                                        <Stack spacing={2}>
                                            {statusData.warnings && statusData.warnings.length > 0 && (
                                                <Stack spacing={1}>
                                                    <Typography variant="subtitle2" fontWeight="bold">Warnings</Typography>
                                                    {statusData.warnings.map((warning, idx) => (
                                                        <Alert key={idx} severity="warning">
                                                            <strong>{warning.code}:</strong> {warning.message}
                                                        </Alert>
                                                    ))}
                                                </Stack>
                                            )}
                                            {statusData.critical_errors && statusData.critical_errors.length > 0 && (
                                                <Stack spacing={1}>
                                                    <Typography variant="subtitle2" fontWeight="bold">Critical Errors</Typography>
                                                    {statusData.critical_errors.map((err, idx) => (
                                                        <Alert key={idx} severity="error">
                                                            <strong>{err.code}:</strong> {err.message}
                                                            {err.exception_type && (
                                                                <Typography variant="caption" display="block">
                                                                    ({err.exception_type})
                                                                </Typography>
                                                            )}
                                                        </Alert>
                                                    ))}
                                                </Stack>
                                            )}
                                        </Stack>
                                    )}
                                </Box>
                            )}

                            {/* Files Tab */}
                            {activeTab === 'files' && (
                                <Box sx={{ p: 3 }}>
                                    <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 2 }}>Run Files</Typography>
                                    <RunFileBrowser runId={runId!} />
                                    <Box sx={{ mt: 3 }}>
                                        <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 2 }}>Downloads</Typography>
                                        <DownloadActions runId={runId!} />
                                    </Box>
                                </Box>
                            )}
                            {/* Signatures Tab */}
                            {activeTab === 'signatures' && (
                                <Box sx={{ p: 3 }}>
                                    {signatures && signatures.signatures && signatures.signatures.length > 0 ? (
                                        <Stack spacing={2}>
                                            {signatures.signatures.map((sig, idx) => (
                                                <Box key={idx} sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                                                    <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
                                                        <Stack spacing={0.5}>
                                                            <Typography variant="subtitle2" fontWeight="bold">
                                                                Segment: {sig.segment}
                                                            </Typography>
                                                            <Typography variant="body2" color="text.secondary">
                                                                Generator: {sig.generator}
                                                            </Typography>
                                                            {sig.signature && (
                                                                <Typography variant="body2" sx={{ mt: 1, fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                                                    {sig.signature.length > 100 ? sig.signature.substring(0, 100) + '...' : sig.signature}
                                                                </Typography>
                                                            )}
                                                        </Stack>
                                                        <Stack direction="row" spacing={1}>
                                                            {sig.generator === 'topology_less_pdb' && (
                                                                <Button
                                                                    variant="outlined"
                                                                    size="small"
                                                                    href={`/runs/${runId}/download/topology-less-pdb?segment=${sig.segment}`}
                                                                    download
                                                                >
                                                                    Download Topology-less PDB
                                                                </Button>
                                                            )}
                                                            {sig.generator === 'ca_only_pdb' && (
                                                                <Button
                                                                    variant="outlined"
                                                                    size="small"
                                                                    href={`/runs/${runId}/download/ca-only-pdb?segment=${sig.segment}`}
                                                                    download
                                                                >
                                                                    Download CA-only PDB
                                                                </Button>
                                                            )}
                                                        </Stack>
                                                    </Stack>
                                                </Box>
                                            ))}
                                        </Stack>
                                    ) : (
                                        <Typography variant="body2" color="text.secondary">
                                            No signatures available for this run.
                                        </Typography>
                                    )}
                                </Box>
                            )}
                        </Paper>
                    </>
                )}

                {!statusData && !error && (
                    <Alert severity="info">Loading run data...</Alert>
                )}
            </Stack>

            {/* Log Viewer Dialog */}
            <LogViewer runId={runId!} open={logOpen} onClose={() => setLogOpen(false)} />
        </>
    );
};

export default RunResults;
