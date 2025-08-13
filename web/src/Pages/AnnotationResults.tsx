import React, { useEffect, useState } from "react"
import {
    Alert,
    Box,
    Grid,
    Skeleton,
    Stack,
    Tab,
    Tabs,
    Typography,
    Paper,
    Link,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Table,
    TableBody,
    TableCell,
    TableRow,
    TableHead,
    IconButton,
    Button,
    LinearProgress
} from "@mui/material"
import { styled } from "@mui/system";
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import DownloadIcon from '@mui/icons-material/Download'

import { useParams } from "react-router-dom"
import DownloadMetadataActions from "../Components/DownloadMetadata"
import SessionStatus from "../Components/SessionStatus"
import MDViewer from "../Components/MDViewer"
import TasksProgressBar, { Task, TaskStatus } from "../Components/TasksProgressBar";
import ListFiles from "../Components/ListFiles";
export type FileType = 'tpr' | 'gro' | 'top' | 'opt'

const HeatmapProgress = styled(LinearProgress)(({ theme }) => ({
    height: 10,
    borderRadius: 5,
    [`& .MuiLinearProgress-bar`]: {
        background: "linear-gradient(to right, #a8e6a1, #2e7d32)", // white to light green (#a8e6a1) to dark green (#2e7d32)
    },
}));

interface ConfidenceBarProps {
    confidence?: number | null;
}

const ConfidenceBar: React.FC<ConfidenceBarProps> = ({ confidence }) => {
    if (confidence == null) { // catches both null and undefined
        return <Typography color="text.secondary">Confidence of identification: N/A</Typography>;
    }

    const value = confidence; // number, safe

    return (
        <Box>
            <Typography variant="body2" color="text.secondary">
                Confidence: {value.toFixed(1)}%
            </Typography>
            <HeatmapProgress variant="determinate" value={value} />
        </Box>
    );
};

export interface AnnotationResultsStatusResponse {
    uuid: string
    status: 'pending' | 'processing' | 'completed' | 'failed'
    processed_files: { [key: string]: string }
    created: string
    expires: string
    options: { [key: string]: any }
    error?: string
}

const AnnotationResults = () => {
    const { session } = useParams<{ session: string }>()
    const [loading, setLoading] = useState(true)
    const [statedata, setStateData] = useState<AnnotationResultsStatusResponse>({
        uuid: '',
        processed_files: {},
        status: 'pending',
        created: '',
        expires: '',
        options: {}
    })
    const [error, setError] = useState<any>(null)
    const [segments, setSegments] = useState<string[]>([])
    const [selectedSegment, setSelectedSegment] = useState<string>("SIMULATION")
    const [segmentInfo, setSegmentInfo] = useState<{
        name: string | null
        confidence: number | null
        db_crosslink: string | null
        identifier: string | null,
        ident: string | null,
    }>({
        name: null,
        confidence: null,
        db_crosslink: null,
        identifier: null,
        ident: null,
    })


    const TASK_TYPES_ORDER = [
        { key: "Load", prefix: "Load simulation" },
        { key: "Resolve<br>Signatures", prefix: "Generate fragment signatures" },
        { key: "Resolve<br>Identifiers", prefix: "Resolve signatures to identifiers" },
        { key: "Summarize", prefix: "Summarize results" },
        { key: "Annotation<br>Complete", prefix: "Download metadata for results" },
    ];

    const [tasks, setTasks] = useState<Task[]>(TASK_TYPES_ORDER.map(t => ({
        type: t.key,
        fullName: "",
        status: "unknown" as TaskStatus,
        statusText: ""
    })));

    useEffect(() => {
        (async function fetchStatus() {
            try {
                const response = await fetch(`/api/annotate/${session}`)
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`)
                }
                const data = await response.json()
                setStateData(data)
                if (data.status === 'pending' || data.status === 'processing') {
                    setTimeout(fetchStatus, 5000)
                }
            } catch (err) {
                setError(err)
            }
        })()
    }, [session])

    useEffect(() => {

        fetch(`/api/annotate/${session}/results/tasks`)
            .then(res => {
                if (!res.ok) throw new Error(`Tasks log not available`);
                return res.json();
            })
            .then((data: Record<string, string>) => {
                console.log("Fetched tasks data:", data);
                const newTasks: Task[] = TASK_TYPES_ORDER.map(t => {
                    const entry = Object.entries(data).find(([name]) =>
                        name.toLowerCase().startsWith(t.prefix.toLowerCase())
                    );

                    if (!entry) {
                        console.warn(`No matching log entry found for prefix: "${t.prefix}"`);
                        return {
                            type: t.key,
                            fullName: t.key,   // use key here instead of empty string
                            status: "unknown",
                            statusText: ""
                        };
                    }

                    const [, rawStatus] = entry;  // ignore the fullName from API here

                    const statusLower = rawStatus.toLowerCase();
                    let status: TaskStatus = "unknown";
                    if (statusLower.includes("ok")) status = "ok";
                    else if (statusLower.includes("failed")) status = "failed";

                    return {
                        type: t.key,
                        fullName: t.key,  // always use the key here
                        status,
                        statusText: rawStatus
                    };
                });
                setTasks(newTasks);
            })
            .catch((err) => {
                console.error("Error fetching or processing tasks:", err);
            });

        if (statedata.status === 'completed') {
            setLoading(false)
            fetch(`/api/annotate/${session}/results/segments`)
                .then(res => res.json())
                .then(segmentList => {
                    setSegments(segmentList)
                    setSelectedSegment("SIMULATION")
                })
                .catch(err => setError(err))

            fetch(`/api/annotate/${session}/results/errors`)
                .then(res => {
                    if (!res.ok) return "";
                    return res.json(); // API returns jsonify(string)
                })
                .then((errStr: string) => {
                    if (errStr && errStr.trim().length > 0) {
                        setError(new Error(errStr));
                    }
                })
                .catch(() => {
                    // ignore errors here
                });

        } else if (statedata.status === 'failed') {
            setLoading(false)
            setError(new Error(`Session ${session} failed`))
        }
    }, [statedata])

    useEffect(() => {
        if (!selectedSegment || selectedSegment === "SIMULATION") {
            setSegmentInfo({
                name: null,
                confidence: null,
                db_crosslink: null,
                identifier: null,
                ident:null
            })
            return
        }

        const fetchSegmentInfo = async () => {
            try {
                const [name, confidence, db_crosslink, identifier, ident] = await Promise.all([
                    fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/name`).then(res => res.json()),
                    fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/confidence`).then(res => res.json()),
                    fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/db_crosslink`).then(res => res.json()),
                    fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/identifier`).then(res => res.json()),
                    fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/accession`).then(res => res.json())
                ])

                setSegmentInfo({
                    name,
                    confidence,
                    db_crosslink,
                    identifier,
                    ident
                })
            } catch (err) {
                console.error(err)
            }
        }

        fetchSegmentInfo()
    }, [selectedSegment, session])

    const handleTabChange = (_: any, newValue: string) => {
        setSelectedSegment(newValue)
    }
    // New states for SIMULATION data
    const [simAtoms, setSimAtoms] = useState<number | null>(null)
    const [simBonds, setSimBonds] = useState<number | null>(null)
    const [simMolecules, setSimMolecules] = useState<number | null>(null)

    // Flags and signatures for non-SIMULATION tabs
    const [segmentFlags, setSegmentFlags] = useState<Record<string, boolean>>({})
    const [signatures, setSignatures] = useState<
        {
            name: string
            type?: string
            description?: string
            short?: string
            full?: string
            filename?: string
            identifiers?: {
                exists: boolean
                name?: string
                description?: string
                identity?: string[]
                similarity?: Record<string, number>
                sim_metric?: string[]
            }[]
        }[]
    >([])

    // Loading states for flags and signatures
    const [loadingFlags, setLoadingFlags] = useState(false)
    const [loadingSignatures, setLoadingSignatures] = useState(false)

    // Fetch SIMULATION data (atoms, bonds, molecules)
    useEffect(() => {
        if (selectedSegment === "SIMULATION") {
            setSimAtoms(null)
            setSimBonds(null)
            setSimMolecules(null)

            const base = `/api/annotate/${session}/results/sim`
            fetch(`${base}/atoms`)
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (typeof data === 'number') setSimAtoms(data)
                }).catch(() => {})

            fetch(`${base}/bonds`)
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (typeof data === 'number') setSimBonds(data)
                }).catch(() => {})

            fetch(`${base}/molecules`)
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (Array.isArray(data)) setSimMolecules(data.length)
                }).catch(() => {})
        }
    }, [selectedSegment, session])

    // Fetch flags and signatures for non-SIMULATION tabs
    useEffect(() => {
        if (!selectedSegment || selectedSegment === "SIMULATION") {
            setSegmentFlags({})
            setSignatures([])
            return
        }
        setLoadingFlags(true)
        setLoadingSignatures(true)

        // Fetch flags list
        fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/flags`)
            .then(res => {
                if (!res.ok) throw new Error("Flags not available")
                return res.json() as Promise<string[]>
            })
            .then(async (flagsList) => {
                const flagsObj: Record<string, boolean> = {}
                // For each flag, fetch its boolean value
                await Promise.all(flagsList.map(async flag => {
                    try {
                        const res = await fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/flag_${flag}`)
                        if (!res.ok) return
                        const val = await res.json() as boolean
                        flagsObj[flag] = val
                    } catch {}
                }))
                setSegmentFlags(flagsObj)
            })
            .catch(() => setSegmentFlags({}))
            .finally(() => setLoadingFlags(false))

        // Fetch signatures list
        fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/signatures`)
            .then(res => {
                if (!res.ok) throw new Error("Signatures not available")
                return res.json() as Promise<string[]>
            })
            .then(async (signatureNames) => {
                const sigs = await Promise.all(signatureNames.map(async (sigName) => {
                    try {
                        const [type, description, shortSig, fullSig, filename] = await Promise.all([
                            fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/signature/${sigName}/type`).then(r => r.ok ? r.json() : null),
                            fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/signature/${sigName}/description`).then(r => r.ok ? r.json() : null),
                            fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/signature/${sigName}/short`).then(r => r.ok ? r.json() : null),
                            fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/signature/${sigName}/full`).then(r => r.ok ? r.json() : null),
                            fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/signature/${sigName}/filename`).then(r => r.ok ? r.json() : null),
                        ])

                        // Fetch identifiers info for this signature
                        // We will try to fetch identifiers if exist
                        let identifiers = []
                        const existsRes = await fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/identifiers/${sigName}/exists`)
                        const exists = existsRes.ok ? await existsRes.json() : false
                        if (exists) {
                            const [idName, idDesc, identity, similarity, sim_metric] = await Promise.all([
                                fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/identifiers/${sigName}/name`).then(r => r.ok ? r.json() : null),
                                fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/identifiers/${sigName}/description`).then(r => r.ok ? r.json() : null),
                                fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/identifiers/${sigName}/identity`).then(r => r.ok ? r.json() : []),
                                fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/identifiers/${sigName}/similarity`).then(r => r.ok ? r.json() : {}),
                                fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/intermediate/identifiers/${sigName}/similarity_kind`).then(r => r.ok ? r.json() : null),
                            ])
                            identifiers.push({
                                exists: true,
                                name: idName,
                                description: idDesc,
                                identity,
                                similarity,
                                sim_metric,
                            })
                        }

                        return {
                            name: sigName,
                            type,
                            description,
                            short: shortSig,
                            full: fullSig,
                            filename,
                            identifiers,
                        }
                    } catch {
                        return { name: sigName, identifiers: [] }
                    }
                }))
                setSignatures(sigs)
            })
            .catch(() => setSignatures([]))
            .finally(() => setLoadingSignatures(false))

    }, [selectedSegment, session])

    // Download handler for full signature text
    const downloadTextFile = (filename: string, content: string) => {
        const blob = new Blob([content], { type: "text/plain;charset=utf-8" })
        const url = URL.createObjectURL(blob)
        const link = document.createElement("a")
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
    }

    return (
        <>
            {error && <Alert sx={{ mb: 3 }} severity="error">{error.message}</Alert>}

            <Stack direction="column" spacing={5} sx={{ width: "100%" }}>
                <Stack
                    direction="row"
                    spacing={5}
                    sx={{ width: "100%", alignItems: "flex-start" }}
                >
                    {/* Left column */}
                    <Stack spacing={1} sx={{ flex: 1 }}>
                        <Typography variant="h1">Annotation details</Typography>
                        <Typography>Session ID: {session}</Typography>
                        <Typography>
                            Job status: <SessionStatus>{statedata?.status || ""}</SessionStatus>
                        </Typography>
                        <Typography>
                            Session Expiration: {(new Date(statedata?.expires)).toLocaleString()}
                        </Typography>
                    </Stack>

                    {/* Right column */}
                    <Stack spacing={2} sx={{ flex: 1 }}>
                        <Typography variant="h3">Annotation process</Typography>
                        <Box sx={{ display: "flex", alignItems: "center", width: "100%", overflowX: "auto", pb: 2 }}>
                            <TasksProgressBar tasks={tasks} />
                        </Box>
                        <Typography variant="h3">Files</Typography>
                        <ListFiles session={session} />
                    </Stack>
                </Stack>

                {loading ? skeleton : (
                    <>
                        <Typography variant="h2">Detected Biomolecules</Typography>
                        <Grid container spacing={3}>
                            <Grid item xs={12} md={6}>
                                <Box sx={{
                                    border: '1px solid #ddd',
                                    borderRadius: '8px',
                                    overflow: 'hidden'
                                }}>
                                    <MDViewer
                                        session={session!}
                                        width={600}
                                        height={600}
                                        segment={selectedSegment === "SIMULATION" ? "system" : selectedSegment}
                                        segments={segments}
                                    />
                                </Box>
                            </Grid>

                            <Grid item xs={12} md={6}>
                                <Paper elevation={2} sx={{ p: 2 }}>
                                    <Tabs
                                        value={selectedSegment}
                                        onChange={handleTabChange}
                                        variant="scrollable"
                                        scrollButtons="auto"
                                    >
                                        {segments.map((seg) => (
                                            <Tab key={seg} label={seg} value={seg} />
                                        ))}
                                    </Tabs>

                                    <Box sx={{ mt: 2 }}>
                                        {selectedSegment === "SIMULATION" ? (
                                            <>
                                                <Typography color="text.secondary" sx={{ mb: 1 }}>
                                                    This view displays the complete simulation system.
                                                </Typography>
                                                <Typography>Number of atoms: {simAtoms !== null ? simAtoms : "N/A"}</Typography>
                                                <Typography>Number of bonds: {simBonds !== null ? simBonds : "N/A"}</Typography>
                                            </>
                                        ) : (
                                            <>
                                                {segmentInfo.identifier ? (
                                                    <>
                                                        <Typography variant="h4">{segmentInfo.ident}</Typography>
                                                        <Typography variant="h6" color="text.secondary">{segmentInfo.name}</Typography>

                                                        {segmentInfo.db_crosslink && (
                                                            <Typography>
                                                                Database reference: <Link href={segmentInfo.db_crosslink} target="_blank" rel="noopener">
                                                                {segmentInfo.db_crosslink}
                                                            </Link>
                                                            </Typography>
                                                        )}
                                                        <Box sx={{ minHeight: 4, width: "100%" }}>&nbsp;</Box>
                                                        <ConfidenceBar confidence={segmentInfo.confidence} />
                                                    </>
                                                ) : (
                                                    <Typography>No segment information available.</Typography>
                                                )}
                                                <Box sx={{ minHeight: 8, width: "100%" }}>&nbsp;</Box>
                                                <Accordion>
                                                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                                        <Typography variant="h6">Identification details</Typography>
                                                    </AccordionSummary>
                                                    <AccordionDetails>
                                                        <Box sx={{ mt: 3 }}>
                                                            <Typography variant="h5">Available information for identification</Typography>
                                                            {loadingFlags ? (
                                                                <Skeleton width={200} />
                                                            ) : Object.keys(segmentFlags).length === 0 ? (
                                                                <Typography color="text.secondary">No flags available.</Typography>
                                                            ) : (
                                                                <Table size="small" sx={{ mt: 1 }}>
                                                                    <TableHead>
                                                                        <TableRow>
                                                                            <TableCell>Flag</TableCell>
                                                                            <TableCell>Value</TableCell>
                                                                        </TableRow>
                                                                    </TableHead>
                                                                    <TableBody>
                                                                        {Object.entries(segmentFlags).map(([flag, val]) => (
                                                                            <TableRow key={flag}>
                                                                                <TableCell>{flag}</TableCell>
                                                                                <TableCell>{val ? "True" : "False"}</TableCell>
                                                                            </TableRow>
                                                                        ))}
                                                                    </TableBody>
                                                                </Table>
                                                            )}
                                                        </Box>

                                                        <Box sx={{ mt: 4 }}>
                                                            <Typography variant="h5">Signatures</Typography>
                                                            {loadingSignatures ? (
                                                                <Skeleton width={200} />
                                                            ) : signatures.length === 0 ? (
                                                                <Typography color="text.secondary">No signatures found.</Typography>
                                                            ) : (
                                                                signatures.map(sig => (
                                                                    <Accordion key={sig.name} sx={{ mb: 1 }}>
                                                                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                                                            <Typography sx={{ fontWeight: "bold" }}>
                                                                                {sig.type ? `${sig.type}` : "UNKNOWN"} {`(${sig.name})`}
                                                                            </Typography>
                                                                        </AccordionSummary>
                                                                        <AccordionDetails>
                                                                            {sig.description && <Typography sx={{ mb: 1 }}>{sig.description}</Typography>}
                                                                            <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", mb: 1 }}>
                                                                                {sig.short || "No short info available."}
                                                                            </Typography>
                                                                            {sig.full && sig.filename && (
                                                                                <Button
                                                                                    startIcon={<DownloadIcon />}
                                                                                    onClick={() => downloadTextFile(sig.filename!, sig.full!)}
                                                                                    variant="outlined"
                                                                                    sx={{ mb: 2 }}
                                                                                >
                                                                                    Download Full Signature
                                                                                </Button>
                                                                            )}

                                                                            {/* Identifiers nested accordions */}
                                                                            {sig.identifiers && sig.identifiers.length > 0 ? sig.identifiers.map((id, idx) => (
                                                                                <Accordion key={idx} sx={{ ml: 2 }}>
                                                                                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                                                                        <Typography>Identifier: {id.name || "Unnamed"}</Typography>
                                                                                    </AccordionSummary>
                                                                                    <AccordionDetails>
                                                                                        {id.description && <Typography sx={{ mb: 1 }}>{id.description}</Typography>}
                                                                                        {id.identity && id.identity.length > 0 && (
                                                                                            <>
                                                                                                <Typography variant="subtitle2">Identity:</Typography>
                                                                                                <ul>
                                                                                                    {id.identity.map((val, i) => <li key={i}>{val}</li>)}
                                                                                                </ul>
                                                                                            </>
                                                                                        )}
                                                                                        {id.similarity && Object.keys(id.similarity).length > 0 && (
                                                                                            <>
                                                                                                <Typography variant="subtitle2">Similarity:</Typography>
                                                                                                <Table size="small" sx={{ maxWidth: 300 }}>
                                                                                                    <TableHead>
                                                                                                        <TableRow>
                                                                                                            <TableCell>Target</TableCell>
                                                                                                            <TableCell>{id.sim_metric || "Similarity"}</TableCell>
                                                                                                        </TableRow>
                                                                                                    </TableHead>
                                                                                                    <TableBody>
                                                                                                        {Object.entries(id.similarity)
                                                                                                            .sort(([, a], [, b]) => b - a) // sort by value descending
                                                                                                            .map(([target, val]) => (
                                                                                                                <TableRow key={target}>
                                                                                                                    <TableCell>{target}</TableCell>
                                                                                                                    <TableCell>{val} %</TableCell>
                                                                                                                </TableRow>
                                                                                                            ))}
                                                                                                    </TableBody>
                                                                                                </Table>
                                                                                            </>
                                                                                        )}
                                                                                    </AccordionDetails>
                                                                                </Accordion>
                                                                            )) : <Typography>No identifiers available.</Typography>}
                                                                        </AccordionDetails>
                                                                    </Accordion>
                                                                ))
                                                            )}
                                                        </Box>
                                                    </AccordionDetails>
                                                </Accordion>
                                            </>
                                        )}
                                    </Box>
                                </Paper>
                            </Grid>
                        </Grid>
                    </>
                )}
            </Stack>
            <Box sx={{ mt: 3, display: "flex", gap: 2 }}>
                <DownloadMetadataActions uuid={statedata.uuid} what="results" />
                <DownloadMetadataActions uuid={statedata.uuid} what="log" />
            </Box>
        </>
    )
}

const skeleton = (
    <Stack direction="column" spacing={5} sx={{ width: "100%" }}>
        <Skeleton variant="text" width="60%" />
        <Skeleton variant="text" width="40%" />
        <Skeleton variant="text" width="50%" />
        <Grid container spacing={3}>
            <Grid item xs={12} md={3}>
                <Skeleton variant="rectangular" height={200} />
            </Grid>
            <Grid item xs={12} md={9}>
                <Skeleton variant="rectangular" height={200} />
            </Grid>
        </Grid>
    </Stack>
)

export default AnnotationResults
