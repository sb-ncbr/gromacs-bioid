import React, { useEffect, useState } from "react";
import { Box, Typography, CircularProgress } from "@mui/material";

interface ListFilesProps {
    session?: string;
}

const ListFiles: React.FC<ListFilesProps> = ({ session }) => {
    const [provided, setProvided] = useState<string[]>([]);
    const [used, setUsed] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!session) {
            setProvided([]);
            setUsed([]);
            setLoading(false);
            return;
        }

        let isMounted = true;

        const fetchFiles = async () => {
            try {
                const [providedRes, usedRes] = await Promise.all([
                    fetch(`/api/annotate/${session}/results/files/provided`),
                    fetch(`/api/annotate/${session}/results/files/used`),
                ]);

                const providedData = providedRes.ok ? await providedRes.json() : [];
                const usedData = usedRes.ok ? await usedRes.json() : [];

                if (isMounted) {
                    setProvided(providedData);
                    setUsed(usedData);
                }
            } catch (err) {
                console.error("Failed to fetch files:", err);
                if (isMounted) {
                    setProvided([]);
                    setUsed([]);
                }
            } finally {
                if (isMounted) setLoading(false);
            }
        };

        setLoading(true);
        fetchFiles();

        return () => {
            isMounted = false;
        };
    }, [session]);

    if (!session) {
        return <Typography variant="body2" color="text.secondary">No session</Typography>;
    }

    if (loading) {
        return <CircularProgress size={20} />;
    }

    if (provided.length === 0) {
        return <Typography variant="body2" color="text.secondary">No files provided</Typography>;
    }

    return (
        <Box sx={{ overflowX: "auto", display: "flex", gap: 1, pb: 1 }}>
            {provided.map((file) => {
                const isUsed = used.includes(file);
                return (
                    <Typography
                        key={file}
                        variant="body2"
                        sx={{
                            whiteSpace: "nowrap",
                            color: isUsed ? "success.main" : "text.secondary",
                            fontWeight: isUsed ? 600 : 400,
                        }}
                    >
                        {file}
                    </Typography>
                );
            })}
        </Box>
    );
};

export default ListFiles;
