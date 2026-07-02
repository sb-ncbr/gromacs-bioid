import { Stack, Grid, Typography, Button, IconButton, Table, TableCell, TableRow, TableBody, Box, Alert, Tooltip, Switch, FormControlLabel, Dialog, DialogTitle, DialogContent, DialogActions, TextField } from "@mui/material"
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
    run_name?: string | null;
}

const MINIMAL_DEFAULT_CONFIG = {
    executor: {
        n_threads: 10,
        tps: 100,
        emit_queue_stats: true,
        signatures_parallel: false,
        identifiers_parallel: false,
        verification_parallel: false,
    },
    loader: {
        tpr_resid_from_one: true,
        guess_missing_elements: true,
        guess_missing_masses: true,
        guess_missing_names: true,
        guess_missing_bonds: false,
        quick_structure_search: true,
        element_mass_tolerance: 0.01,
        bond_guess_vdw_factor: 0.55,
        unwrap_periodic_boundaries: true,
        unwrap_compound: "fragments",
        unwrap_reference: "com",
        unwrap_selection: "all",
        unwrap_guess_bonds_if_missing: true,
        unwrap_warn_if_jumps_detected: true,
        unwrap_max_bond_length_factor: 0.5,
        unwrap_max_backbone_gap: 10.0,
    },
    signatures: {
        overwrite_existing: false,
        generation_attempts: 10,
        smiles_maximum_number_of_atoms: 250,
        fasta_map_determine_sequence_partial_mode: false,
        fasta_map_determine_sequence_strict_mode: false,
        name_minimum_length: 1,
        smiles: true,
        smiles_not_sanitized: true,
        atom: true,
        fasta_map_protein: true,
        fasta_map_nucleic: true,
        fasta_resname_protein: true,
        fasta_resname_nucleic: true,
        pdb_protein: true,
        pdb_nucleic: true,
        pdb_not_sanitized_protein: true,
        pdb_not_sanitized_nucleic: true,
        pdb_backbone_protein: true,
        pdb_backbone_nucleic: true,
        pdb_backbone_not_sanitized_protein: true,
        pdb_backbone_not_sanitized_nucleic: true,
        name_chain: true,
        name_molecule: true,
        name_segment: true,
        fingerprint: true,
        inchi_key: true,
        morgan_fingerprint: true,
        selfies: true,
        molecular_formula: true,
        tdi: true,
        lipid_shorthand: true,
        glycan_composition: true,
        mmcif: true,
        topology_less_pdb: true,
        ca_only_pdb: true,
    },
    identifiers: {
        overwrite_existing: false,
        blast_pdb_protein: true,
        blast_pdb_protein_similarity: true,
        blast_uniprot: true,
        blast_uniprot_similarity: true,
        blast_pdb_nucleic: true,
        blast_pdb_nucleic_similarity: true,
        pdb_struct_protein: true,
        pdb_struct_protein_similarity: true,
        pdb_struct_nucleotide: true,
        pdb_struct_nucleotide_similarity: true,
        alphafind_struct: true,
        alphafind_struct_similarity: true,
        chembl_struct: true,
        chembl_struct_similarity: true,
        pubchem_struct: true,
        pubchem_struct_similarity: true,
        atom: true,
        atom_similarity: false,
        idsm_pubchem: true,
        idsm_pubchem_similarity: true,
        idsm_chembl: true,
        idsm_chembl_similarity: true,
        idsm_chebi: true,
        idsm_chebi_similarity: true,
        name_ccd: true,
        name_ccd_similarity: false,
        name_maps: true,
        name_maps_similarity: false,
        name_manual: true,
        name_manual_similarity: false,
    },
    verification: {
        verify_top_n: 100,
        similarity_top_n: 10,
        enable_annotation_quality: true,
        resolver_weight: 0.4,
        similarity_weight: 0.4,
        annotation_weight: 0.2,
        tm_score_threshold: 0.5,
        min_final_confidence: 0.0,
    },
    timeouts: {
        global_timeout_s: 600,
        input_timeout_s: 5,
        create_timeout_s: 5,
        load_timeout_s: 300,
        signatures_timeout_s: 2400,
        identifiers_timeout_s: 1200,
        summarize_timeout_s: 1200,
        metadata_timeout_s: 1200,
    },
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
    const handleRerunAll = async () => {
        setRerunLoading(true);
        setRerunError(null);
        setRerunSuccessCount(null);
        try {
            const res = await fetch('/runs/rerun-all', { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                setRerunSuccessCount(data.count);
                await fetchRuns();
            } else {
                const errorText = await res.text();
                setRerunError(errorText || "Failed to re-run all");
            }
        } catch (err) {
            setRerunError(err instanceof Error ? err.message : "An error occurred");
        } finally {
            setRerunLoading(false);
        }
    };

    const [uploadedFiles, setUploadedFiles] = useState<FileWithPath[]>([])
    const [analyzing, setAnalyzing] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [runs, setRuns] = useState<RunListItem[]>([])
    const [defaultConfig, setDefaultConfig] = useState<Record<string, any> | null>(null)
    const [customConfigEnabled, setCustomConfigEnabled] = useState(false)
    const [editedConfig, setEditedConfig] = useState<Record<string, any>>({})
    const [runName, setRunName] = useState<string>("")
    const [configDialogOpen, setConfigDialogOpen] = useState(false)
    const [fastModeEnabled, setFastModeEnabled] = useState(false)
    const [rerunDialogOpen, setRerunDialogOpen] = useState(false);
    const [rerunLoading, setRerunLoading] = useState(false);
    const [rerunError, setRerunError] = useState<string | null>(null);
    const [rerunSuccessCount, setRerunSuccessCount] = useState<number | null>(null);

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
            const res = await fetch('/runs/config/default')
            if (res.ok) {
                const data = await res.json()
                setDefaultConfig(data)
                setEditedConfig(data)
            } else {
                console.error("Failed to fetch default config: status", res.status)
                const body = await res.text()
                console.error("Response body:", body)
                setDefaultConfig(MINIMAL_DEFAULT_CONFIG)
                setEditedConfig(MINIMAL_DEFAULT_CONFIG)
            }
        } catch (err) {
            console.error("Failed to fetch default config:", err)
            setDefaultConfig(MINIMAL_DEFAULT_CONFIG)
            setEditedConfig(MINIMAL_DEFAULT_CONFIG)
        }
    }

    const setParallelFlags = (config: Record<string, any>, enabled: boolean) => {
        const updated = { ...config }
        if (!updated.executor) updated.executor = {}
        updated.executor = { ...updated.executor }
        updated.executor.signatures_parallel = enabled
        updated.executor.identifiers_parallel = enabled
        updated.executor.verification_parallel = enabled
        return updated
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
        
        // Send run_name if provided
        if (runName) {
            data.append('run_name', runName)
        }
        
        // Append config_json if custom config or fast mode is enabled
        if ((customConfigEnabled || fastModeEnabled) && editedConfig) {
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
        // Try to get title from run_name, then input_kind, then fallback to run_id
        if (run.run_name) {
            return run.run_name
        }
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
                            <Stack direction="row" spacing={2} alignItems="center">
                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={customConfigEnabled}
                                            onChange={(e) => {
                                                const checked = e.target.checked
                                                setCustomConfigEnabled(checked)
                                                if (!checked) {
                                                    setEditedConfig(defaultConfig || MINIMAL_DEFAULT_CONFIG)
                                                    setFastModeEnabled(false)
                                                }
                                                setConfigDialogOpen(checked)
                                            }}
                                        />
                                    }
                                    label="Customize configuration"
                                />
                                {customConfigEnabled && (
                                    <Button variant="outlined" size="small" onClick={() => setConfigDialogOpen(true)}>
                                        Edit Config
                                    </Button>
                                )}
                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={fastModeEnabled}
                                            onChange={(e) => {
                                                const checked = e.target.checked
                                                setFastModeEnabled(checked)
                                                if (checked) {
                                                    setCustomConfigEnabled(true)
                                                    setEditedConfig(prev => setParallelFlags(prev, true))
                                                } else {
                                                    setEditedConfig(prev => setParallelFlags(prev, false))
                                                }
                                            }}
                                        />
                                    }
                                    label="Run in Fast Mode (parallel)"
                                />

                            </Stack>


                        </Stack>
                        {/* Config Editor Dialog */}
                        <Dialog
                            open={configDialogOpen}
                            onClose={() => setConfigDialogOpen(false)}
                            maxWidth="md"
                            fullWidth
                        >
                            <DialogTitle>Customize Configuration</DialogTitle>
                            <DialogContent>
                                {editedConfig && Object.keys(editedConfig).length > 0 ? (
                                    <ConfigEditor config={editedConfig} onChange={setEditedConfig} />
                                ) : (
                                    <Typography variant="body2" color="text.secondary">
                                        Failed to load configuration. Using fallback defaults.
                                    </Typography>
                                )}
                            </DialogContent>
                            <DialogActions>
                                <Button onClick={() => setConfigDialogOpen(false)} variant="contained">
                                    Done
                                </Button>
                            </DialogActions>
                        </Dialog>

                        {/* Run name input */}
                        <TextField
                            label="Run name (optional)"
                            value={runName}
                            onChange={(e) => setRunName(e.target.value)}
                            fullWidth
                            sx={{ mt: 2 }}
                        />

                        <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ mt: 2 }}>
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
                    <Stack direction="row" spacing={2} alignItems="center">
                        <Typography variant="h2">Recent Annotations</Typography>
                        {runs.length > 0 && (
                            <Tooltip title="Re-queue all existing runs with their original input files and config">
                                <Button
                                    variant="outlined"
                                    color="secondary"
                                    size="small"
                                    onClick={() => setRerunDialogOpen(true)}
                                    disabled={rerunLoading}
                                >
                                    Re-run All
                                </Button>
                            </Tooltip>
                        )}
                    </Stack>
                    {rerunSuccessCount !== null && (
                        <Alert severity="success" sx={{ mt: 1 }}>
                            Re-queued {rerunSuccessCount} runs.
                        </Alert>
                    )}
                    {rerunError && (
                        <Alert severity="error" sx={{ mt: 1 }}>
                            {rerunError}
                        </Alert>
                    )}
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

            {/* Re-run All Confirmation Dialog */}
            <Dialog
                open={rerunDialogOpen}
                onClose={() => !rerunLoading && setRerunDialogOpen(false)}
            >
                <DialogTitle>Re-run all annotations?</DialogTitle>
                <DialogContent>
                    <Typography variant="body2">
                        This will create new runs for all {runs.length} existing annotations using their original input files and config. Old runs will not be deleted.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button
                        onClick={() => setRerunDialogOpen(false)}
                        disabled={rerunLoading}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleRerunAll}
                        variant="contained"
                        disabled={rerunLoading}
                    >
                        {rerunLoading ? "Re-running..." : "Re-run All"}
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    )
}

export default Frontpage
