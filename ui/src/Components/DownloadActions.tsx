import { Button, Stack } from "@mui/material";
import { Download } from "@mui/icons-material";
import { useState } from "react";

interface DownloadActionsProps {
    runId: string;
}

const DownloadActions: React.FC<DownloadActionsProps> = ({ runId }) => {
    const [configExists, setConfigExists] = useState<boolean | null>(null);

    const downloadResultsJson = async () => {
        try {
            const response = await fetch(`/runs/${runId}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `results-${runId}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error("Failed to download results:", err);
        }
    };

    const downloadLog = async (type: "normal" | "debug") => {
        try {
            const response = await fetch(`/runs/${runId}/logs?type=${type}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const text = await response.text();
            
            const blob = new Blob([text], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `run-${runId}${type === "debug" ? ".debug" : ""}.log`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error("Failed to download log:", err);
        }
    };

    const downloadConfig = async () => {
        try {
            // First check if config exists with HEAD request
            const headResponse = await fetch(`/files/${runId}/config.ini`, { method: "HEAD" });
            if (!headResponse.ok) {
                console.warn("Config file not found");
                setConfigExists(false);
                return;
            }
            setConfigExists(true);
            
            // Trigger download
            const link = document.createElement('a');
            link.href = `/files/${runId}/config.ini`;
            link.download = `config-${runId}.ini`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (err) {
            console.error("Failed to download config:", err);
            setConfigExists(false);
        }
    };

    return (
        <Stack direction="row" spacing={2}>
            <Button
                variant="outlined"
                startIcon={<Download />}
                onClick={downloadResultsJson}
            >
                Download Results JSON
            </Button>
            <Button
                variant="outlined"
                startIcon={<Download />}
                onClick={() => downloadLog("normal")}
            >
                Download Normal Logs
            </Button>
            <Button
                variant="outlined"
                startIcon={<Download />}
                onClick={() => downloadLog("debug")}
            >
                Download Debug Logs
            </Button>
            <Button
                variant="outlined"
                startIcon={<Download />}
                onClick={downloadConfig}
                disabled={configExists === false}
            >
                Download Config
            </Button>
        </Stack>
    );
};

export default DownloadActions;
