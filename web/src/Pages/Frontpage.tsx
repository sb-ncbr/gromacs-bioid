import { Stack, Grid, Typography, Button, IconButton, Table, TableCell, TableRow, TableBody, Dialog, DialogTitle, DialogContent, DialogActions, Box, Alert, AlertTitle, Tooltip, Tab, TextField, Divider } from "@mui/material"
import Dropzone from "../Components/Dropzone"
import Example from "../Components/Example"
import { Link, useNavigate } from "react-router-dom"
import { use, useEffect, useState } from "react"
import { CheckCircle, Edit, Help, RemoveCircle } from "@mui/icons-material"
import { FileWithPath } from "react-dropzone/."
import FormsWrapped from "../Components/FormsWrapper"
import customMetadataSchema from "../schemas/custom-metadata.schema.json"
import customMetadataUISchema from "../schemas/custom-metadata.ui.schema.json"
import Sessions, { AnnotationSessionRecord } from "../Components/Sessions"

const Frontpage = () => {
    const navigate = useNavigate()


    const [uploaded, setUploaded] = useState(false)
    const [uploadedFiles, setUploadedFiles] = useState<FileWithPath[]>([])
    const [analyzing, setAnalyzing] = useState(false)

    const [error, setError] = useState<boolean>(false)

    const clearFiles = () => {
        setUploaded(false)
        setAnalyzing(false)
        setError(false)
    }

    const clearFile = (file: FileWithPath) => {
        setUploadedFiles(uploadedFiles.filter(f => f !== file))
        setError(false)
    }

    const editFile = async () => {
        setAnalyzing(true)

        let data = new FormData()
        for (const [index, value] of uploadedFiles.entries()) {
            data.append(`file-${index}`, value)
        }

        const request_id = await fetch('/api/annotate', { body: data, method: 'POST' })
            .then(response => response.text())
            .then(text => JSON.parse(text))
            .then(data => data.uuid)
            .catch(error => setError(true))


        setAnalyzing(false)

        if (request_id) {
            const storedRequests = JSON.parse(localStorage.getItem('request_ids') || '[]');
            var record: AnnotationSessionRecord = {
                id: request_id,
                title: customMetadata?.dataset_metadata?.title || uploadedFiles.filter(file => file.name.endsWith('.tpr') || file.name.endsWith('.zip') || file.name.endsWith('.tar') || file.name.endsWith('.gz'))[0]?.name || "Untitled",
                uploadedFiles: uploadedFiles.map(file => file.name),
                date: new Date().toISOString()
            }
            storedRequests.push(record);
            localStorage.setItem('request_ids', JSON.stringify(storedRequests));
            navigate(`/results/${request_id}`)
        }
        
        if (error) {
            console.error("Error has occured while analyzing file", error)
            return
        }
    }

    const [customMetadataModalState, setCustomMetadataModalState] = useState(false)
    const [customMetadataConfirm, setCustomMetadataConfirm] = useState(false)
    const [customMetadataEditor, setCustomMetadataEditor] = useState<"form" | "textfield">("form")
    const [customMetadataEditorValue, setCustomMetadataEditorValue] = useState("")

    const switchEditor = () => {
        if (customMetadataEditor === "form") 
            setCustomMetadataEditorValue(JSON.stringify(customMetadata, null, 2))
        else {
            try {
                setCustomMetadata(JSON.parse(customMetadataEditorValue))
            } catch (e) {
                console.error("Error parsing JSON", e)
            }
        }
        setCustomMetadataEditor(customMetadataEditor === "form" ? "textfield" : "form")
    }

    const fileSuffix = (name: string) => {
        return name.split('.').pop() || ""
    }

    const shortName = (name: string) => {
        return name.length > 35 ? name.substring(0, 35) + "...." + fileSuffix(name): name
    }

    interface CustomMetadata {
        dataset_metadata?: {
            title?: string;
            creator?: string;
            publishing_institution?: string;
            publication_year?: number;
        };
    }

    const [customMetadata, setCustomMetadata] = useState<CustomMetadata>({})
    const setCustomAnnotations = (value: boolean) => {
        setCustomMetadataModalState(false)
        // if (!value) setCustomMetadata({})
        // setCustomMetadataConfirm(value)
        const customMetadataBlob = new Blob([JSON.stringify(customMetadata)], { type: 'application/json' });
        const customMetadataFile = new File([customMetadataBlob], 'md.custom-metadata', { type: 'application/json' });
        setUploadedFiles([...uploadedFiles, customMetadataFile as FileWithPath]);
    }

    return (
        <>
            <Stack direction="column" spacing={6}>
                <Typography variant="body1">
                    {/* Placeholder introduction text */}
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

                <Grid container spacing={3} alignItems="stretch" sx={{ mt: 3 }}>
                    <Grid item xs={12} md={8}>
                        <Dropzone
                            setUploadedFiles={setUploadedFiles}
                            setUploaded={setUploaded}
                        />

                        {(uploadedFiles.length > 0 || customMetadataConfirm) && (
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
                                                        {(file.name === "md.custom-metadata" || file.name === "md.custom-metadata.json") && (
                                                            <Tooltip title="Edit annotations" arrow>
                                                                <IconButton onClick={() => setCustomMetadataModalState(true)}>
                                                                    <Edit />
                                                                </IconButton>
                                                            </Tooltip>
                                                        )}
                                                    </Stack>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </Stack>
                        )}

                        <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ mt: 3 }}>
                            <Tooltip title="Begin annotation process" arrow>
                                <Button
                                    variant="contained"
                                    size="large"
                                    sx={{ width: "100%" }}
                                    onClick={editFile}
                                    disabled={(!customMetadataConfirm && !uploadedFiles.length) || analyzing}
                                >
                                    Start Annotation
                                </Button>
                            </Tooltip>
                        </Stack>

                        {error && (
                            <Alert severity="error" sx={{ mt: 2 }}>
                                <AlertTitle>Error</AlertTitle>
                                An error occurred during processing. Please try again. {error}
                            </Alert>
                        )}
                    </Grid>

                    <Grid item xs={12} md={4}>
                        {/* Reserved for future UI or help section */}
                    </Grid>
                </Grid>

                <Sessions />
            </Stack>
        </>
    )
}

export default Frontpage
