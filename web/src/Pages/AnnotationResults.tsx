import {Alert, Box, Button, Grid, Paper, Skeleton, Stack, Typography, Link} from "@mui/material"
import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import FilePreview from "../Components/FilePreview"
import DownloadMetadataActions from "../Components/DownloadMetadata"
import { set } from "yaml/dist/schema/yaml-1.1/set"
import SessionStatus from "../Components/SessionStatus"

type FileType = 'tpr' | 'gro' | 'top' | 'opt';

export interface AnnotationResultsStatusResponse {
    uuid: string
    status: 'pending' | 'processing' | 'completed' | 'failed'
    processed_files: {
        [key: string]: string
    }
    created: string
    expires: string
    options: {
        [key: string]: any}
    error?: string
    message?: string
    trace?: string
}

const AnnotationResults = () => {

    const navigate = useNavigate();

    const { session } = useParams<{ session: string }>()
    
    const [loading, setLoading] = useState(true)
    const [data, setData] = useState<Object>({})
    const [waitingTime, setWaitingTime] = useState<number>(0)
    const [statedata, setStateData] = useState<AnnotationResultsStatusResponse>({
        uuid: '',
        processed_files: {},
        status: 'pending',
        created: '',
        expires: '',
        options: {}
        
    })
    const [error, setError] = useState<any>(null)

    useEffect(() => {

        (async function fetchStatus() {
            try {
                const response = await fetch(`/api/annotate/${session}`);
                if (!response.ok) {
                    if (response.status === 404) {
                        throw new Error(`Session ${session} not found`);
                    }
                    if (response.status === 400) {
                        throw new Error(`Session ${session} is not ready yet`);
                    }
                    if (response.status === 500) {
                        throw new Error(`Server error, try again.`);
                    }
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();

                setStateData(data);
                if (data.status === 'pending' || data.status === 'processing') {
                    setWaitingTime((prev: number) => prev + 1);
                    setTimeout(fetchStatus, 5000);
                }

            } catch (error) {
                setError(error);
            }
        })();
    }, [session])

    useEffect(() => {
        console.log(`Waiting time: ${waitingTime} seconds`)
    }, [waitingTime])

    useEffect(() => {
        if (statedata.status === 'completed' || statedata.status === 'failed') {
            setLoading(false)
            fetch(`/api/annotate/${session}/results`)
            .then(response => {
                if (!response.ok) {
                    if (response.status === 404) {
                        throw new Error(`Session ${session} not found`)
                    }
                    if (response.status === 400) {
                        throw new Error(`Session ${session} is not ready yet`)
                    }
                    if (response.status === 500) {
                        throw new Error(`Server error, try again.`)
                    }
                    throw new Error(`HTTP error! status: ${response.status} ${response.text}`);
                }
                return response.json()
            })
            .then(data => {
                if (data.error) {
                    setError(new Error(data.error + (data.error_message ? `\nError Message: ${data.error_message}` : '')));
                }
                setData(data)
            })
            .catch(error => setError(error))
        } else if (statedata.status === 'failed') {
            setLoading(false)
            setError(new Error(`Session ${session} failed`))
        }
    }, [statedata])


    const optionalFileTypes: FileType[] = ['tpr', 'gro', 'top', 'opt']
    console.log(error)
    return (
        <>
            
                        {/* <Paper sx={{ p: 2, display: "flex", mb: 3}}> */}
                            <Stack direction="column" sx={{width: "100%"}} spacing={5} alignItems="stretch" whiteSpace={"pre-line"}>
                                <Stack direction="column" spacing={1}>
                                    <Typography variant="h1">Annotation results</Typography>
                                    <Typography>Session ID: {session}</Typography>
                                    <Typography>Job status: <SessionStatus>{statedata?.status || ""}</SessionStatus></Typography>
                                    <Typography>Session Expiration: {(new Date(statedata?.expires)).toLocaleString()}</Typography>
                                    {waitingTime >= 3 && statedata.status !== 'completed' && statedata.status !== 'failed' ? (
                                        <Alert severity="info" sx={{mt: 2}}>
                                            <Typography variant="h3" sx={{fontWeight: "bold"}}>This might take a while.</Typography>Sit back and relax or visit <Link href={window.location.toString()} sx={{fontWeight: "bold"}}>{window.location.toString()}</Link> again in a short moment.
                                        </Alert>
                                        ) : null}
                                </Stack>
                                {loading ? (
                                    skeleton
                                ) : error ? (
                                    <Alert severity="error" sx={{ mt: 2 }}>
                                        <Typography variant="h3" sx={{ fontWeight: "bold" }}>No valid result was generated!</Typography>
                                        <Typography variant="body1" sx={{color: "initial", mt:1, mb:1}}>{error.message}</Typography>
                                        <Button variant="contained" onClick={() => navigate(-1)}>Go Back</Button>
                                    </Alert>
                                ) : (
                                    <>
                                    <Typography variant="h1">Results</Typography>
                                    <Box sx={{ mt: 3 }}>
                                        <Typography variant="h3">Raw JSON Output</Typography>
                                        <pre
                                            style={{
                                                backgroundColor: "#f5f5f5",
                                                padding: "1rem",
                                                borderRadius: "8px",
                                                overflowX: "auto",
                                            }}
                                        >
                        {JSON.stringify(data, null, 2)}
                    </pre>
                                    </Box>
                                    <Stack direction="row" justifyItems={"left"} spacing={1}>
                                    <DownloadMetadataActions stateData={statedata} data={data} />
                                    </Stack>
                                    </>
                                )}
                            </Stack>
                        {/* </Paper> */}
        </>
    )
}

const skeleton = (
    <Stack direction="column" sx={{width: "100%"}} spacing={5} alignItems="stretch" whiteSpace={"pre-line"}>
    <Stack direction="column" spacing={1}>
        <Skeleton variant="text" width="60%" />
        <Skeleton variant="text" width="40%" />
        <Skeleton variant="text" width="50%" />
    </Stack>
    <Grid container spacing={1} alignItems="stretch">
        {[...Array(3)].map((_, index) => (
            <Grid item xs={12} sm={6} md={4} key={index}>
                <Skeleton variant="rectangular" height={118} />
            </Grid>
        ))}
    </Grid>
    <Stack direction="row" justifyItems={"left"} spacing={1}>
        <Skeleton variant="rectangular" width={150} height={40} />
        <Skeleton variant="rectangular" width={150} height={40} />
    </Stack>
    </Stack>
)

export default AnnotationResults
