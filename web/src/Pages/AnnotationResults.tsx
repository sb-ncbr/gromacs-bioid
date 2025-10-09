import React, {JSX, useEffect, useState} from "react"
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
import ShowLoad from "../Components/render/ShowLoad";
import ShowSignatures from "../Components/render/ShowSignatures";
import ShowIdentifiers from "../Components/render/ShowIdentifiers";
import ShowVerification from "../Components/render/ShowVerification";
import ShowComplete from "../Components/render/ShowComplete";
import MDViewer from "../Components/MDComponents/MDViewer"
import TasksProgressBar, { Task, TaskStatus } from "../Components/TasksProgressBar";
import ListFiles from "../Components/ListFiles";


interface CommonPageProps {
    uuid: string;
}

const TASK_PAGES: Record<string, (props: CommonPageProps) => JSX.Element> = {
    "Load Simulation": (props) => <ShowLoad {...props} />,
    "Resolve Signatures": (props) => <ShowSignatures {...props} />,
    "Resolve Identifiers": (props) => <ShowIdentifiers {...props} />,
    "Summarize Results": (props) => <ShowVerification {...props} />,
    "Annotation Complete": (props) => <ShowComplete {...props} />,
};

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
    const [activePage, setActivePage] = useState<string | null>(null);

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
        { key: "Load Simulation", prefix: "Load simulation" },
        { key: "Resolve Signatures", prefix: "Generate fragment signatures" },
        { key: "Resolve Identifiers", prefix: "Resolve signatures to identifiers" },
        { key: "Summarize Results", prefix: "Summarize results" },
        { key: "Annotation Complete", prefix: "Download metadata for results" },
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

                {/* Progress bar section */}
                <Stack spacing={2} sx={{ width: "100%" }}>
                    <Typography variant="h1">Annotation process</Typography>

                    <Box sx={{ display: "flex", alignItems: "center", width: "100%", overflowX: "auto", pb: 2 }}>
                        <TasksProgressBar tasks={tasks} onSelect={(taskType) => setActivePage(taskType)} />
                    </Box>

                    {/* Session details as small text below */}
                    <Stack spacing={0.5} sx={{ color: "text.secondary", fontSize: "0.85rem" }}>
                        <Typography variant="body2">Session ID: {session}</Typography>
                        <Typography variant="body2">
                            Job status: <SessionStatus>{statedata?.status || ""}</SessionStatus>
                        </Typography>
                        <Typography variant="body2">
                            Session Expiration: {(new Date(statedata?.expires)).toLocaleString()}
                        </Typography>
                    </Stack>

                    <Box
                        sx={{
                            width: "100%",
                            my: 2,          // vertical margin
                            lineHeight: "0.8rem",
                            fontSize: "0.8rem",
                            color: "transparent", // text invisible
                            userSelect: "none",
                        }}
                    >
                        {"<br><br><br>"}
                    </Box>

                    {activePage ? (
                        TASK_PAGES[activePage]({ uuid: statedata.uuid })
                    ) : (
                        <Typography variant="h3">Please select the step from progressbar</Typography>
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
