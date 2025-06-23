import React from 'react';
import { Chip, Paper, Stack, Tooltip, Typography } from '@mui/material';
import { CheckCircle, CircleOutlined } from '@mui/icons-material';

type FilePreviewProps = {
    fileType: string;
    description?: string;
    file?: string;
    isUploaded?: boolean;
};

const FilePreview: React.FC<FilePreviewProps> = ({fileType, description, file, isUploaded}) => {


    return (
        <Paper sx={{p: 2, display: "flex", mb: 3, borderColor: "primary.main", border: 1, height: "100%" }}>
            <Stack direction="column" spacing={1}>
            <>
                <Stack direction="row" spacing={1}>
                    {isUploaded ? <Tooltip title="File provided" arrow placement='top'><CheckCircle sx={{color: 'green'}} /></Tooltip> :
                    <Tooltip title="File not provided" arrow placement='top'><CircleOutlined sx={{color: 'primary.secondary'}} /></Tooltip>}
                    <Typography variant="h3" marginRight={1}>
                        {fileType.toLocaleUpperCase()}        
                    </Typography>
                </Stack>    
                <Typography variant="subtitle2" marginLeft={1}>
                    {description}
                </Typography>
                {file ? <Typography variant="body1" marginLeft={1}>
                    <Chip label={file.length > 20 ? file.substring(0, 20) + "..." + file.split('.').pop() : file} color="primary" variant="outlined" />
                        
                    {/* {file.path} */}
                </Typography> : <Typography variant="body1" marginLeft={1}>
                    Not provided
                </Typography>}
                
                <Stack direction="row" spacing={1}>
                    {/* <IconButton onClick={() => {}} color="secondary">
                        <Delete />
                    </IconButton> */}
                </Stack>
            </>
            </Stack>
        </Paper>
    );
};

export default FilePreview;