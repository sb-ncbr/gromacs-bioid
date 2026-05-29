import { useEffect, useState } from "react";
import { Box, List, ListItem, ListItemText, ListItemIcon, Typography, CircularProgress, Link } from "@mui/material";
import { Download as DownloadIcon } from "@mui/icons-material";

interface RunFileBrowserProps {
    runId: string;
}

interface RunFilesResponse {
    run_id: string;
    files: string[];
}

const RunFileBrowser: React.FC<RunFileBrowserProps> = ({ runId }) => {
    const [files, setFiles] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchFiles = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await fetch(`/runs/${runId}/files`);
                if (res.ok) {
                    const data: RunFilesResponse = await res.json();
                    setFiles(data.files || []);
                } else {
                    setError("Failed to fetch files");
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to fetch files");
            } finally {
                setLoading(false);
            }
        };

        fetchFiles();
    }, [runId]);

    if (loading) {
        return (
            <Box sx={{ display: "flex", justifyContent: "center", p: 2 }}>
                <CircularProgress size={24} />
            </Box>
        );
    }

    if (error) {
        return (
            <Typography variant="body2" color="error" sx={{ p: 1 }}>
                {error}
            </Typography>
        );
    }

    if (files.length === 0) {
        return (
            <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>
                No files found
            </Typography>
        );
    }

    return (
        <List dense sx={{ maxHeight: 300, overflow: "auto" }}>
            {files.map((file) => (
                <ListItem
                    key={file}
                    secondaryAction={
                        <ListItemIcon>
                            <Link
                                href={`/files/${runId}/${file}`}
                                download
                                sx={{ display: "flex", alignItems: "center" }}
                            >
                                <DownloadIcon fontSize="small" />
                            </Link>
                        </ListItemIcon>
                    }
                >
                    <ListItemText
                        primary={file}
                        sx={{ "& .MuiListItemText-primary": { fontSize: "0.875rem" } }}
                    />
                </ListItem>
            ))}
        </List>
    );
};

export default RunFileBrowser;
