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
    Link
} from "@mui/material"

import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import DownloadMetadataActions from "../Components/DownloadMetadata"
import SessionStatus from "../Components/SessionStatus"
import MDViewer from "../Components/MDViewer"

export type FileType = 'tpr' | 'gro' | 'top' | 'opt'

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
        identifier: string | null
    }>({
        name: null,
        confidence: null,
        db_crosslink: null,
        identifier: null
    })

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
        if (statedata.status === 'completed') {
            setLoading(false)
            fetch(`/api/annotate/${session}/results/segments`)
                .then(res => res.json())
                .then(segmentList => {
                    setSegments(segmentList)
                    setSelectedSegment("SIMULATION")
                })
                .catch(err => setError(err))
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
                identifier: null
            })
            return
        }

        const fetchSegmentInfo = async () => {
            try {
                const [name, confidence, db_crosslink, identifier] = await Promise.all([
                    fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/name`).then(res => res.json()),
                    fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/confidence`).then(res => res.json()),
                    fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/db_crosslink`).then(res => res.json()),
                    fetch(`/api/annotate/${session}/results/segment/${selectedSegment}/identifier`).then(res => res.json())
                ])

                setSegmentInfo({
                    name,
                    confidence,
                    db_crosslink,
                    identifier
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

    return (
        <>
            {error && <Alert sx={{ mb: 3 }} severity="error">{error.message}</Alert>}

            <Stack direction="column" spacing={5} sx={{ width: "100%" }}>
                <Stack spacing={1}>
                    <Typography variant="h1">Annotation results</Typography>
                    <Typography>Session ID: {session}</Typography>
                    <Typography>
                        Job status: <SessionStatus>{statedata?.status || ""}</SessionStatus>
                    </Typography>
                    <Typography>
                        Session Expiration: {(new Date(statedata?.expires)).toLocaleString()}
                    </Typography>
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
                                        segment={selectedSegment == "SIMULATION" ? "system" : selectedSegment}
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
                                        {selectedSegment !== "SIMULATION" && segmentInfo.name ? (
                                            <>
                                                <Typography variant="h4">{segmentInfo.name}</Typography>
                                                <Typography color="text.secondary">
                                                    Confidence: {segmentInfo.confidence ?? "N/A"}
                                                </Typography>
                                                {segmentInfo.db_crosslink && (
                                                    <Typography>
                                                        DB Link: <Link href={segmentInfo.db_crosslink} target="_blank" rel="noopener">
                                                        {segmentInfo.db_crosslink}
                                                    </Link>
                                                    </Typography>
                                                )}
                                                <Typography>
                                                    Identifier: {segmentInfo.identifier ?? "N/A"}
                                                </Typography>
                                            </>
                                        ) : (
                                            <Typography color="text.secondary">
                                                {selectedSegment === "SIMULATION"
                                                    ? "This view displays the complete simulation system."
                                                    : "No data available for this segment."}
                                            </Typography>
                                        )}
                                    </Box>
                                </Paper>
                            </Grid>
                        </Grid>

                        <Box sx={{ mt: 3, display: "flex", gap: 2 }}>
                            <DownloadMetadataActions uuid={statedata.uuid} what="results" />
                            <DownloadMetadataActions uuid={statedata.uuid} what="log" />
                        </Box>
                    </>
                )}
            </Stack>
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
