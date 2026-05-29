import { Stack, Grid, Typography, Button, IconButton, Table, TableCell, TableRow, TableBody, Box, Alert, Tooltip, Paper, Switch, FormControlLabel } from "@mui/material"
import Dropzone from "../Components/Dropzone"
import ConfigEditor from "../Components/ConfigEditor"
import { useNavigate } from "react-router-dom"
import { useState, useEffect } from "react"
import { CheckCircle, RemoveCircle } from "@mui/icons-material"
import { FileWithPath } from "react-dropzone"

interface RunListItem {
    run_id: string;
    status: string;
    created_at: string;
    input_kind?: string | null;
}

const Frontpage = () => {
    const navigate = useNavigate()

    const formatDate = (dateStr: string | undefined | null): string => {
        if (!dateStr) return "—";
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return "—";
        return d.toLocaleDateString();
    };

    const handleDeleteRun = async (runId: string) => {
        if (!window.confirm("Are you sure you want to delete this run?")) return;
        try {
            const res = await fetch(`/runs/${runId}`, { method: 'DELETE' });
            if (res.ok) {
                await fetchRuns();
            } else {
                console.error("Failed to delete run:", await res.text());
            }
        } catch (err) {
            console.error("Error deleting run:", err);
        }
    };

    const [uploadedFiles, setUploadedFiles] = useState<FileWithPath[]>([])
    const [analyzing, setAnalyzing] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [runs, setRuns] = useState<RunListItem[]>([])
    const [defaultConfig, setDefaultConfig] = useState<Record<string, any> | null>(null)
    const [customConfigEnabled, setCustomConfigEnabled] = useState(false)
    const [editedConfig, setEditedConfig] = useState<Record<string, any>>({})

    useEffect(() => {
        fetchRuns()
        fetchDefaultConfig()
    }, [])

    const fetchRuns = async () => {
        try {
            const res = await fetch('/runs')
            if (res.ok) {
                const data = await res.json()
                setRuns(data.runs || [])
            }
        } catch (err) {
            console.error("Failed to fetch runs:", err)
        }
    }

    const fetchDefaultConfig = async () => {
        try {
            const res = await fetch('/config/default')
            if (res.ok) {
                const data = await res.json()
                setDefaultConfig(data)
                setEditedConfig(data)
            }
        } catch (err) {
            console.error("Failed to fetch default config:", err)
        }
    }

    const clearFile = (file: FileWithPath) => {
        setUploadedFiles(uploadedFiles.filter(f => f !== file))
        setError(null)
    }

    const handleSubmit = async () => {
        setAnalyzing(true)
        setError(null)

        const data = new FormData()
        for (const file of uploadedFiles) {
            data.append('files', file)
        }
        
        // Send customized config if enabled
        if (customConfigEnabled && editedConfig) {
            data.append('config_json', JSON.stringify(editedConfig))
        }

        try {
            const response = await fetch('/runs', {
                method: 'POST',
                body: data
            })

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`)
            }

            const result = await response.json()
            
            // Refresh runs list
            await fetchRuns()
            
            navigate(`/runs/${result.run_id}`)
        } catch (err) {
            setError(err instanceof Error ? err.message : "An error occurred during upload")
            setAnalyzing(false)
        }
    }

    const fileSuffix = (name: string) => {
        return name.split('.').pop() || ""
    }

    const shortName = (name: string) => {
        return name.length > 35 ? name.substring(0, 35) + "...." + fileSuffix(name): name
    }

    const getRunTitle = (run: RunListItem): string => {
        // Try to get title from input_kind or use run_id
        if (run.input_kind) {
            return run.input_kind
        }
        return run.run_id.substring(0, 8) + "..."
    }

    return (
        <>
            <Stack direction="column" spacing={6}>
                <Typography variant="body1">
                    This tool is designed to assist you in annotating molecular simulation datasets by automatically identifying
                    the biomolecules present in the system. It analyzes the uploaded files to extract molecular information such as PDB IDs, InChIKeys, atomic numbers,
                    and other chemical identifiers essential for annotation backed with reputable databases.
                    The tool works independently — simply upload your simulation files, and it will process them without any additional input.
                    After the analysis, you can review, edit, and export the annotations in JSON for integration with repositories or use in publications.
                </Typography>

                <Stack direction="row" spacing={2} alignItems="center">
                    <Typography variant="h2">Molecular Annotation Tool</Typography>
                    <Tooltip title="View Documentation">
                        <Button
                            href="https://www.google.com"
                            size="small"
                            variant="outlined"
                            target="_blank"
                        >
                            Docs
                        </Button>
                    </Tooltip>
                </Stack>

                <Typography variant="body1">
                    This tool analyzes GROMACS molecular dynamics simulation files to identify and annotate the biomolecules present.
                    It is designed to work with a flexible, best-effort approach — simply upload all the files you have from your simulation,
                    and the tool will make use of as much information as possible. The following files are supported:
                </Typography>
                <Box component="ul" sx={{ pl: 4, mb: 2 }}>
                    <li>
                        <Typography variant="body1">
                            <strong>Topology files</strong>: either a <code>.tpr</code> file, a complete <code>.top</code> file, or a <code>.top</code> file with all necessary <code>.itp</code> includes.
                        </Typography>
                    </li>
                    <li>
                        <Typography variant="body1">
                            <strong>Coordinate files</strong>: ideally a <code>.gro</code> file to extract atom positions and structural context.
                        </Typography>
                    </li>
                </Box>
                <Typography variant="body1">
                    Please note: if your simulation topology file contains ".itp" includes, it is necessary that all includes are present for the analysis. This could mean
                    that you need to upload the force-field folder with all necessary files. You may upload everything as .zip archive.
                </Typography>

                <Grid container spacing={3} alignItems="stretch" sx={{ mt: 3 }}>
                    <Grid item xs={12} md={8}>
                        <Dropzone
                            setUploadedFiles={setUploadedFiles}
                        />

                        {uploadedFiles.length > 0 && (
                            <Stack spacing={2} sx={{ p: 2 }}>
                                <Typography variant="h4">Files to Annotate</Typography>
                                <Table size="small" sx={{ width: "100%" }}>
                                    <TableBody>
                                        {uploadedFiles.map((file, index) => (
                                            <TableRow key={index}>
                                                <TableCell sx={{ width: "70%" }}>
                                                    {shortName(file.name)}
                                                </TableCell>
                                                <TableCell sx={{ width: "20%" }}>
                                                    <Stack direction="row" spacing={1} alignItems="center">
                                                        <CheckCircle sx={{ color: 'primary.main' }} />
                                                        {fileSuffix(file.name).toUpperCase()}
                                                    </Stack>
                                                </TableCell>
                                                <TableCell sx={{ width: "10%" }}>
                                                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                                                        <Tooltip title="Remove file" arrow>
                                                            <IconButton onClick={() => clearFile(file)}>
                                                                <RemoveCircle />
                                                            </IconButton>
                                                        </Tooltip>
                                                    </Stack>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </Stack>
                        )}

                        {/* Run Configuration Section */}
                        <Stack spacing={2} sx={{ p: 2, mt: 2 }}>
                            <Typography variant="h4">Run Configuration</Typography>
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={customConfigEnabled}
                                        onChange={(e) => setCustomConfigEnabled(e.target.checked)}
                                    />
                                }
                                label="Customize configuration"
                            />
                            {customConfigEnabled && defaultConfig && (
                                <Paper elevation={0} sx={{ p: 2, border: "1px solid #ccc" }}>
                                    <ConfigEditor config={defaultConfig} onChange={setEditedConfig} />
                                </Paper>
                            )}
                        </Stack>

                        <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ mt: 3 }}>
                            <Tooltip title="Begin annotation process" arrow>
                                <Button
                                    variant="contained"
                                    size="large"
                                    sx={{ width: "100%" }}
                                    onClick={handleSubmit}
                                    disabled={uploadedFiles.length === 0 || analyzing}
                                >
                                    Start Annotation
                                </Button>
                            </Tooltip>
                        </Stack>

                        {error && (
                            <Alert severity="error" sx={{ mt: 2 }}>
                                An error occurred during processing. Please try again. {error}
                            </Alert>
                        )}
                    </Grid>

                    <Grid item xs={12} md={4}>
                        {/* Reserved for future UI or help section */}
                    </Grid>
                </Grid>

                {/* Run History */}
                <Stack spacing={3} sx={{ mt: 6 }}>
                    <Typography variant="h2">Recent Annotations</Typography>
                    {runs.length > 0 ? (
                        <Table size="small">
                            <TableBody>
                                {runs.slice(0, 10).map((run) => (
                                    <TableRow key={run.run_id}>
                                        <TableCell>
                                            <Typography variant="body2" fontWeight="bold">
                                                {getRunTitle(run)}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                {run.run_id}
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Typography variant="body2" textTransform="capitalize">
                                                {run.status}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                {formatDate(run.created_at)}
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Button
                                                size="small"
                                                variant="outlined"
                                                onClick={() => navigate(`/runs/${run.run_id}`)}
                                            >
                                                View
                                            </Button>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Button
                                                size="small"
                                                variant="outlined"
                                                color="error"
                                                onClick={() => handleDeleteRun(run.run_id)}
                                            >
                                                Delete
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    ) : (
                        <Typography variant="body2" color="text.secondary">
                            No recent annotations found.
                        </Typography>
                    )}
                </Stack>
            </Stack>
        </>
    )
}

export default Frontpage
