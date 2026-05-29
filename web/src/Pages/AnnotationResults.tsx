import React, {JSX, useEffect, useState} from "react"
import {
    Alert,
    Box,
    Grid,
    Skeleton,
    Stack,
    Typography,
    Tabs, Tab,
    LinearProgress, CircularProgress
} from "@mui/material"
import { styled } from "@mui/system";
import DownloadMetadataActions from "../Components/DownloadMetadata"
import SessionStatus from "../Components/SessionStatus"
import SegmentSelector from "../Components/MDComponents/SegmentSelector"
import MDViewer from "../Components/MDComponents/MDViewer"
import MoleculeSummaryPanel from "../Components/MDComponents/MoleculeSummaryPanel";
import { useParams } from "react-router-dom"

import TasksProgressBar, { Task, TaskStatus } from "../Components/TasksProgressBar";

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
                    setTimeout(() => {
                        window.location.reload();
                    }, 5000);
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
                    setSegments(segmentList.segments)
                    setSelectedSegment("SIMULATION")
                })
                .catch(err => setError(err))

        } else if (statedata.status === 'failed') {
            setLoading(false)
            setError(new Error(`Session ${session} failed`))
        }
    }, [statedata])

    interface SimulationSectionProps {
        session: string;
        selectedSegment: string;
        segments: string[];
    }

    const SimulationSection: React.FC<SimulationSectionProps> = ({
                                                                     session,
                                                                     selectedSegment,
                                                                     segments,
                                                                 }) => {
        const [simulationAvailable, setSimulationAvailable] = useState<boolean | null>(null);

        useEffect(() => {
            const checkSimulationFile = async () => {
                try {
                    const res = await fetch(`/api/annotate/${session}/results/verification/SYSTEM/simulation`, {
                        method: "HEAD",
                    });
                    setSimulationAvailable(res.ok);
                } catch {
                    setSimulationAvailable(false);
                }
            };
            checkSimulationFile();
        }, [session]);

        if (simulationAvailable === null) {
            return (
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        height: 400,
                    }}
                >
                    <CircularProgress size={40} />
                </Box>
            );
        }

        if (!simulationAvailable) {
            return (
                <Box
                    sx={{
                        height: 400,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        bgcolor: "grey.100",
                        borderRadius: 2,
                    }}
                >
                    <Typography variant="body1" color="text.secondary">
                        Simulation view not available.
                    </Typography>
                </Box>
            );
        }

        // Force MDViewer to re-mount completely when segment changes
        return (
            <MDViewer
                key={`${session}-${selectedSegment}`}
                session={session}
                segment={selectedSegment}
                segments={segments}
                width={500}
                height={600}
            />
        );
    };


    return (
        <>
            {error && <Alert sx={{ mb: 3 }} severity="error">{error.message}</Alert>}

                {/* Progress bar section */}
                <Stack spacing={2} sx={{ width: "100%" }}>
                    <Typography variant="h1">Annotation process</Typography>

                    <Box sx={{ display: "flex", alignItems: "center", width: "100%", overflowX: "auto", pb: 2 }}>
                        <TasksProgressBar tasks={tasks} />
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

                    {statedata.uuid ? (
                    <Grid container spacing={2} sx={{ width: "100%", mt: 2 }}>
                        {/* First column — Segment selector (20%) */}
                        <Grid item xs={12} md={2}>
                            <SegmentSelector
                                uuid={statedata.uuid}
                                onSelect={(segmentId, segmentName) => {
                                    console.log("Selected segment:", segmentId, segmentName);
                                    setSelectedSegment(segmentId);
                                }}
                            />
                        </Grid>

                        {/* Second column — Mol* Simulation View (40%) */}
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
                                {selectedSegment ? (
                                    <SimulationSection
                                        session={session!}
                                        selectedSegment={selectedSegment}
                                        segments={segments}
                                    />
                                ) : (
                                    <Typography variant="body2" color="text.secondary">
                                        Select a segment to view the simulation.
                                    </Typography>
                                )}
                            </Box>
                        </Grid>

                        {/* Third column — Placeholder for visualization/summary (40%) */}
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
                                <MoleculeSummaryPanel uuid={statedata.uuid} segment={selectedSegment} />
                            </Box>
                        </Grid>
                    </Grid>
                    ) : (
                        // Show a skeleton / loader while uuid is not yet fetched
                        skeleton
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
