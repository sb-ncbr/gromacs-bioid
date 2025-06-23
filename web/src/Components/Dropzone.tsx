import { FileUpload } from "@mui/icons-material";
import { Box, Divider, Grid, Paper, Stack, Typography } from "@mui/material";
import { useEffect } from "react";
import { FileWithPath, useDropzone } from "react-dropzone";
import { Dispatch, SetStateAction } from "react";
import { useTheme, useMediaQuery } from "@mui/material";

interface DropzoneProps {
    setUploadedFiles: Dispatch<SetStateAction<FileWithPath[]>>;
    setUploaded: Dispatch<SetStateAction<boolean>>;
}



const Dropzone = ({ setUploadedFiles, setUploaded }: DropzoneProps) => {    const {
    acceptedFiles,
    fileRejections,
    getRootProps,
    getInputProps
} = useDropzone({
        accept: {
            'application/octet-stream': [".tpr", ".gro", ".top", ".itp"],
            'application/json': [".json"],
            'text/yaml': [".yaml"],
            'archive/zip': [".zip"],
            'archive/x-tar': [".tar"],
            'application/x-gzip': [".tar.gz"]
            
        }
    });
    
    const theme = useTheme();
    const isVertical = useMediaQuery(theme.breakpoints.up("md"));
    
    useEffect(() => {
        if (acceptedFiles.length > 0) {
            setUploadedFiles((state: FileWithPath[]) => state.concat(acceptedFiles))
        } else {
            // setUploaded(false)
        }
    }, [acceptedFiles])

    
    return (
        <Stack direction="column">
            <Box>
                <Stack direction="column">
                    <Paper elevation={0} sx={{ p: 5, textAlign: "center", border: "2.5px dashed", "&:hover": { borderColor: "#2E7D32", cursor: "pointer" } }} variant="outlined" >
                        <div {...getRootProps({ className: 'dropzone' })}>
                            <input {...getInputProps()} />
                            <Grid container alignItems="center" justifyContent="center" justifyItems={"center"} spacing={2}>
                                <Grid item xs={12} sm={12} md={5} lg={5} xl={5}>
                                    <Stack direction="row" alignItems="center" justifyContent={"center"} spacing={1}>
                                        <FileUpload sx={{ fontSize: "3em", color: "#2E7D32" }} />
                                        <Typography variant="h4">Drag files here</Typography>
                                    </Stack>
                                </Grid>
                                <Grid item xs={12} sm={12} md={1} lg={1} xl={2}>
                                    <Divider orientation={isVertical ? "vertical" : "horizontal"} flexItem={isVertical}>OR</Divider>
                                </Grid>
                                <Grid item xs={12} sm={12} md={6} lg={6} xl={5}>
                                    <Typography variant="h4">Click to select files</Typography>
                                </Grid>
                            </Grid>
                            {/* or archives *.zip or *.tar(.gz) */}
                            <Typography variant="subtitle1"><em>(Only [*.tpr, *.gro, *.top, and *.itp] files are accepted.)</em></Typography>
                        </div>
                    </Paper>
                </Stack>
            </Box>
        </Stack>
    );
}


export default Dropzone;
