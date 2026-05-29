import { useEffect, useState, useRef, useCallback } from "react";
import {
    Alert,
    Box,
    Grid,
    Stack,
    Typography,
    CircularProgress,
    Collapse,
    Paper,
    IconButton,
    Tooltip,
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
import { ExpandMore, ExpandLess, Article, Close } from "@mui/icons-material";

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

interface SignatureInfo {
    segment: string;
    generator: string;
    signature: any;
}

interface SignaturesResponse {
    run_id: string;
    signatures: SignatureInfo[];
    attempted_generators: Record<string, string[]>;
}

interface IdentifierHit {
    identifier: string;
    ident_type: string;
    hit_type: string;
    resolver_name: string;
    score?: number | null;
    database_url?: string | null;
}

interface IdentifiersResponse {
    run_id: string;
    segment: string;
    hits: IdentifierHit[];
    attempted_resolvers: string[];
}

interface VerifiedHitItem {
    identifier: string;
    ident_type: string;
    database: string;
    resolver_score?: number | null;
    similarity_score?: number | null;
    annotation_quality_score?: number | null;
    final_confidence: number;
    is_verified: boolean;
    rejection_reason?: string | null;
    supporting_evidence_count: number;
}

interface VerificationResponse {
    run_id: string;
    segment: string;
    hits: VerifiedHitItem[];
}

const RunResults = () => {
    const { runId } = useParams<{ runId: string }>();
    const [statusData, setStatusData] = useState<RunStatusResponse | null>(null);
    const [initialLoading, setInitialLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [segments, setSegments] = useState<string[]>([]);
    const [selectedSegment, setSelectedSegment] = useState<string>("SYSTEM");
    const [loadingInfo, setLoadingInfo] = useState<LoadingInfoResponse | null>(null);
    const [showLoadingDetails, setShowLoadingDetails] = useState(false);
    const [logOpen, setLogOpen] = useState(false);
    const [selectedStep, setSelectedStep] = useState<string | null>(null);
    const [showEvents, setShowEvents] = useState(false);
    
    // Step detail data
    const [signaturesData, setSignaturesData] = useState<SignaturesResponse | null>(null);
    const [identifiersData, setIdentifiersData] = useState<IdentifiersResponse | null>(null);
    const [verificationData, setVerificationData] = useState<VerificationResponse | null>(null);
    const [stepLoading, setStepLoading] = useState(false);

    // Ref to track latest status for polling decisions
    const latestStatusRef = useRef<RunStatusResponse | null>(null);

    const [segmentMeta, setSegmentMeta] = useState<Record<string, any> | null>(null);

    const fetchMolecules = useCallback(async (id: string) => {
        try {
            const res = await fetch(`/runs/${id}/molecules`);
            if (res.ok) {
                const data: MoleculeSummaryResponse = await res.json();
                setSegments(data.segments || []);
                setSegmentMeta(data.segment_meta || null);
                // Default to SYSTEM instead of first segment
                setSelectedSegment("SYSTEM");
            }
        } catch (err) {
            console.error("Failed to fetch molecules:", err);
        }
    }, []);

    const fetchLoadingInfo = useCallback(async (id: string) => {
        try {
            const res = await fetch(`/runs/${id}/loading`);
            if (res.ok) {
                const data: LoadingInfoResponse = await res.json();
                setLoadingInfo(data);
            }
        } catch (err) {
            console.error("Failed to fetch loading info:", err);
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
                fetchLoadingInfo(data.run_id);

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
    }, [runId, fetchMolecules, fetchLoadingInfo]);

    // Fetch step detail data when selectedStep changes
    useEffect(() => {
        if (!selectedStep || !runId) {
            return;
        }

        const fetchStepData = async () => {
            setStepLoading(true);
            try {
                if (selectedStep === "Resolve Signatures") {
                    const res = await fetch(`/runs/${runId}/signatures`);
                    if (res.ok) {
                        const data: SignaturesResponse = await res.json();
                        setSignaturesData(data);
                    }
                } else if (selectedStep === "Resolve Identifiers") {
                    const res = await fetch(`/runs/${runId}/identifiers`);
                    if (res.ok) {
                        const data: IdentifiersResponse = await res.json();
                        setIdentifiersData(data);
                    }
                } else if (selectedStep === "Annotation Complete") {
                    const res = await fetch(`/runs/${runId}/verification`);
                    if (res.ok) {
                        const data: VerificationResponse = await res.json();
                        setVerificationData(data);
                    }
                }
                // Load Simulation and Summarize Results use already-fetched data
            } catch (err) {
                console.error("Failed to fetch step data:", err);
            } finally {
                setStepLoading(false);
            }
        };

        fetchStepData();
    }, [selectedStep, runId]);

    if (initialLoading) {
        return (
            <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "400px" }}>
                <CircularProgress />
            </Box>
        );
    }

    if (error) {
        return (
            <Alert severity="error">
                {error}
            </Alert>
        );
    }

    if (!statusData) {
        return (
            <Alert severity="warning">
                No status data available
            </Alert>
        );
    }

    const isFailed = statusData.pipeline.status === 'failed';

    const renderStepDetail = () => {
        if (!selectedStep) return null;

        return (
            <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="h3">{selectedStep}</Typography>
                    <IconButton onClick={() => setSelectedStep(null)} size="small">
                        <Close />
                    </IconButton>
                </Stack>
                
                {stepLoading && (
                    <Box sx={{ display: "flex", justifyContent: "center", p: 2 }}>
                        <CircularProgress size={24} />
                    </Box>
                )}

                {!stepLoading && (
                    <Stack spacing={2} sx={{ mt: 1 }}>
                        {selectedStep === "Load Simulation" && (
                            <>
                                <Typography variant="body2">
                                    <strong>Input Kind:</strong> {loadingInfo?.input_kind || statusData.pipeline.input_kind || "N/A"}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>Selected Strategy:</strong> {loadingInfo?.selected_strategy || loadingInfo?.final_strategy || "N/A"}
                                </Typography>
                                {loadingInfo?.topology_files && loadingInfo.topology_files.length > 0 && (
                                    <Typography variant="body2">
                                        <strong>Topology Files:</strong> {loadingInfo.topology_files.join(", ")}
                                    </Typography>
                                )}
                                {loadingInfo?.attempts && loadingInfo.attempts.length > 0 && (
                                    <Box>
                                        <Typography variant="body2"><strong>Attempts:</strong></Typography>
                                        <ul>
                                            {loadingInfo.attempts.map((attempt, idx) => (
                                                <li key={idx}>
                                                    {attempt.strategy}: {attempt.success ? "Success" : `Failed - ${attempt.error}`}
                                                </li>
                                            ))}
                                        </ul>
                                    </Box>
                                )}
                                {statusData.pipeline.input_files && (
                                    <Typography variant="body2">
                                        <strong>Input Files:</strong> {Object.keys(statusData.pipeline.input_files).join(", ")}
                                    </Typography>
                                )}
                            </>
                        )}

                        {selectedStep === "Resolve Signatures" && signaturesData && (
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Segment</TableCell>
                                            <TableCell>Generator</TableCell>
                                            <TableCell>Signature</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {signaturesData.signatures.map((sig, idx) => (
                                            <TableRow key={idx}>
                                                <TableCell>{sig.segment}</TableCell>
                                                <TableCell>{sig.generator}</TableCell>
                                                <TableCell>
                                                    {typeof sig.signature === 'string' 
                                                        ? sig.signature.substring(0, 50) + (sig.signature.length > 50 ? "..." : "")
                                                        : JSON.stringify(sig.signature).substring(0, 50)
                                                    }
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        )}

                        {selectedStep === "Resolve Identifiers" && identifiersData && (
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Identifier</TableCell>
                                            <TableCell>Type</TableCell>
                                            <TableCell>Resolver</TableCell>
                                            <TableCell>Score</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {identifiersData.hits.map((hit, idx) => (
                                            <TableRow key={idx}>
                                                <TableCell>{hit.identifier}</TableCell>
                                                <TableCell>{hit.ident_type}</TableCell>
                                                <TableCell>{hit.resolver_name}</TableCell>
                                                <TableCell>{hit.score ?? "N/A"}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        )}

                        {selectedStep === "Summarize Results" && (
                            <>
                                <Typography variant="body2">
                                    <strong>Total Fragments:</strong> {statusData.tasks.find(t => t.name.toLowerCase().includes('summarize'))?.summary?.total_fragment_count ?? "N/A"}
                                </Typography>
                                {segments.length > 0 && (
                                    <Typography variant="body2">
                                        <strong>Segments:</strong> {segments.join(", ")}
                                    </Typography>
                                )}
                            </>
                        )}

                        {selectedStep === "Annotation Complete" && verificationData && (
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Identifier</TableCell>
                                            <TableCell>Type</TableCell>
                                            <TableCell>Confidence</TableCell>
                                            <TableCell>Verified</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {verificationData.hits.map((hit, idx) => (
                                            <TableRow key={idx}>
                                                <TableCell>{hit.identifier}</TableCell>
                                                <TableCell>{hit.ident_type}</TableCell>
                                                <TableCell>{hit.final_confidence.toFixed(2)}</TableCell>
                                                <TableCell>{hit.is_verified ? "Yes" : "No"}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        )}
                    </Stack>
                )}
            </Paper>
        );
    };

    return (
        <>
            <Stack spacing={3}>
                {/* Title */}
                <Typography variant="h1">Annotation process</Typography>

                {/* Progress bar with logs button */}
                <Box sx={{ display: "flex", alignItems: "center", width: "100%", overflowX: "auto", pb: 2 }}>
                    <TasksProgressBar 
                        tasks={statusData.tasks || []} 
                        onStepClick={setSelectedStep}
                    />
                    <Tooltip title="View Logs">
                        <IconButton onClick={() => setLogOpen(true)} sx={{ ml: 2 }}>
                            <Article />
                        </IconButton>
                    </Tooltip>
                </Box>

                {/* Step detail panel */}
                {renderStepDetail()}

                {/* Session info */}
                <Stack spacing={0.5} sx={{ color: "text.secondary", fontSize: "0.85rem" }}>
                    <Typography variant="body2">Run ID: {statusData.run_id}</Typography>
                    <Typography variant="body2">
                        Status: <strong style={{ textTransform: 'capitalize' }}>{statusData.pipeline.status}</strong>
                    </Typography>
                    {statusData.pipeline.input_kind && (
                        <Typography variant="body2">
                            Input Kind: <strong>{statusData.pipeline.input_kind}</strong>
                        </Typography>
                    )}
                    {statusData.pipeline.input_files && (
                        <Typography variant="body2">
                            Input Files: <strong>{Object.keys(statusData.pipeline.input_files).join(", ")}</strong>
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
                </Stack>

                {/* Failed banner */}
                {isFailed && (
                    <Alert severity="error">
                        Annotation process failed. Check critical errors below.
                    </Alert>
                )}

                {/* Warnings */}
                {statusData.warnings && statusData.warnings.length > 0 && (
                    <Stack spacing={1}>
                        <Typography variant="h3">Warnings</Typography>
                        {statusData.warnings.map((warning, idx) => (
                            <Alert key={idx} severity="warning">
                                <strong>{warning.code}:</strong> {warning.message}
                            </Alert>
                        ))}
                    </Stack>
                )}

                {/* Critical errors */}
                {statusData.critical_errors && statusData.critical_errors.length > 0 && (
                    <Stack spacing={1}>
                        <Typography variant="h3">Critical Errors</Typography>
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

                {/* Loading details collapsible - show whenever loadingInfo exists */}
                {loadingInfo && (
                    <Paper variant="outlined" sx={{ p: 2 }}>
                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                            <Typography variant="h3">Loading Details</Typography>
                            <IconButton onClick={() => setShowLoadingDetails(!showLoadingDetails)}>
                                {showLoadingDetails ? <ExpandLess /> : <ExpandMore />}
                            </IconButton>
                        </Stack>
                        <Collapse in={showLoadingDetails}>
                            <Stack spacing={1} sx={{ mt: 2 }}>
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
                        </Collapse>
                    </Paper>
                )}

                {/* Events collapsible */}
                {statusData.events && statusData.events.length > 0 && (
                    <Paper variant="outlined" sx={{ p: 2 }}>
                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                            <Typography variant="h3">Events</Typography>
                            <IconButton onClick={() => setShowEvents(!showEvents)}>
                                {showEvents ? <ExpandLess /> : <ExpandMore />}
                            </IconButton>
                        </Stack>
                        <Collapse in={showEvents}>
                            <Stack spacing={1} sx={{ mt: 2, maxHeight: 300, overflow: "auto" }}>
                                {statusData.events.slice(-20).reverse().map((event, idx) => (
                                    <Typography key={idx} variant="body2">
                                        <strong>[{event.kind}]</strong> {new Date(event.timestamp).toLocaleTimeString()} - {event.message || "No message"}
                                    </Typography>
                                ))}
                            </Stack>
                        </Collapse>
                    </Paper>
                )}

                {/* Results grid - show whenever segments exist, regardless of pipeline status */}
                {segments.length > 0 ? (
                    <Grid container spacing={2} sx={{ width: "100%", mt: 2 }}>
                        {/* Segment selector (2 columns) */}
                        <Grid item xs={12} md={2}>
                            <Box
                                sx={{
                                    border: "1px solid",
                                    borderColor: "divider",
                                    borderRadius: 2,
                                    p: 0,
                                    height: "100%",
                                }}
                            >
                                <SegmentSelector
                                    segments={segments}
                                    selectedSegment={selectedSegment}
                                    onSelect={setSelectedSegment}
                                    segmentMeta={segmentMeta || undefined}
                                />
                            </Box>
                        </Grid>

                        {/* MD Viewer (5 columns) */}
                        <Grid item xs={12} md={5}>
                            <Box
                                sx={{
                                    border: "1px solid",
                                    borderColor: "divider",
                                    borderRadius: 2,
                                    p: 0,
                                    height: 600,
                                }}
                            >
                                <MDViewer
                                    key={`${runId}-${selectedSegment}`}
                                    runId={runId!}
                                    segment={selectedSegment}
                                    segments={segments}
                                />
                            </Box>
                        </Grid>

                        {/* Molecule Summary Panel (5 columns) */}
                        <Grid item xs={12} md={5}>
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
                                />
                            </Box>
                        </Grid>
                    </Grid>
                ) : (
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                        Segments not yet available.
                    </Typography>
                )}

                {/* Run file browser */}
                <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="h3" sx={{ mb: 1 }}>Run Files</Typography>
                    <RunFileBrowser runId={runId!} />
                </Paper>

                {/* Download actions */}
                <Box sx={{ mt: 3, display: "flex", gap: 2 }}>
                    <DownloadActions runId={runId!} />
                </Box>
            </Stack>

            {/* Log Viewer Dialog */}
            <LogViewer runId={runId!} open={logOpen} onClose={() => setLogOpen(false)} />
        </>
    );
};

export default RunResults;
