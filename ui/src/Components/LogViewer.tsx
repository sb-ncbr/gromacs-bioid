import { useEffect, useRef, useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Tabs,
  Tab,
  Box,
  Typography,
  IconButton,
  Stack,
  Alert,
} from "@mui/material";
import { Close } from "@mui/icons-material";

interface Props {
  runId: string;
  open: boolean;
  onClose: () => void;
}

const LogViewer = ({ runId, open, onClose }: Props) => {
  const [tab, setTab] = useState<"normal" | "debug">("normal");
  const [logText, setLogText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    
    const fetchLogs = async () => {
      try {
        const res = await fetch(`/runs/${runId}/logs?type=${tab}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const text = await res.text();
        setLogText(text);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch logs");
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 500);
    return () => clearInterval(interval);
  }, [open, runId, tab]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logText]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Run Logs — {runId}</Typography>
          <IconButton onClick={onClose}><Close /></IconButton>
        </Stack>
      </DialogTitle>
      <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} textColor="primary" indicatorColor="primary">
          <Tab value="normal" label="Normal" />
          <Tab value="debug" label="Debug" />
        </Tabs>
      </Box>
      <DialogContent dividers sx={{ backgroundColor: "#1e1e1e", color: "#d4d4d4", p: 0 }}>
        {error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <pre
            ref={scrollRef}
            style={{
              margin: 0,
              padding: 16,
              fontFamily: "'Fira Code', 'Courier New', monospace",
              fontSize: "0.85rem",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              maxHeight: "60vh",
              overflowY: "auto",
            }}
          >
            {logText || "Waiting for logs..."}
          </pre>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} variant="outlined">Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default LogViewer;
