import React from "react";
import {
    Box,
    Typography,
    CircularProgress,
    Paper,
    Stack,
    Chip,
    alpha,
} from "@mui/material";
import {
    CheckCircle,
    Error as ErrorIcon,
    Warning as WarningIcon,
    Block,
    RemoveCircle,
    Pending,
} from "@mui/icons-material";
import { TaskInfo } from "../hooks/useSmartPolling";

interface StepCardProps {
    task: TaskInfo;
    isLast: boolean;
    isActive: boolean;
    summaryContent?: React.ReactNode;
    onSelectTab?: () => void;
}

// Helper to format duration
const formatDuration = (startedAt: string | null | undefined, finishedAt: string | null | undefined): string => {
    if (!startedAt || !finishedAt) return "";
    const start = new Date(startedAt);
    const end = new Date(finishedAt);
    const diffMs = end.getTime() - start.getTime();
    if (diffMs < 1000) return "<1s";
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return `${diffSec}s`;
    const diffMin = Math.floor(diffSec / 60);
    const remainingSec = diffSec % 60;
    return `${diffMin}m ${remainingSec}s`;
};

// Helper to format timestamp
const formatTime = (timestamp: string | null | undefined): string => {
    if (!timestamp) return "";
    return new Date(timestamp).toLocaleTimeString();
};

// Get status icon and color
const getStatusIcon = (status: string) => {
    switch (status) {
        case "success":
            return <CheckCircle sx={{ color: "success.main", fontSize: 28 }} />;
        case "failed":
            return <ErrorIcon sx={{ color: "error.main", fontSize: 28 }} />;
        case "warning":
            return <WarningIcon sx={{ color: "warning.main", fontSize: 28 }} />;
        case "running":
            return <CircularProgress size={28} thickness={5} />;
        case "cancelled":
            return <Block sx={{ color: "text.disabled", fontSize: 28 }} />;
        case "skipped":
            return <RemoveCircle sx={{ color: "text.disabled", fontSize: 28 }} />;
        case "pending":
        default:
            return <Pending sx={{ color: "text.disabled", fontSize: 28 }} />;
    }
};

// Get status label
const getStatusLabel = (status: string, isActive: boolean): string => {
    if (isActive && status === "running") return "Running...";
    switch (status) {
        case "success":
            return "Completed";
        case "failed":
            return "Failed";
        case "warning":
            return "Warning";
        case "running":
            return "Running";
        case "cancelled":
            return "Cancelled";
        case "skipped":
            return "Skipped";
        case "pending":
        default:
            return "Waiting...";
    }
};

// Generate summary content based on task type
const getSummaryForTask = (task: TaskInfo): React.ReactNode => {
    const summary = task.summary || {};
    const taskId = task.task_id;

    switch (taskId) {
        case "load_simulation":
            return (
                <Stack direction="row" spacing={1} flexWrap="wrap">
                    {summary.strategy && (
                        <Chip label={`Strategy: ${summary.strategy}`} size="small" variant="outlined" />
                    )}
                </Stack>
            );

        case "analyze_universe":
            return (
                <Stack direction="row" spacing={1} flexWrap="wrap">
                    {summary.segments !== undefined && (
                        <Chip label={`${summary.segments} segment(s)`} size="small" variant="outlined" />
                    )}
                    {summary.unique_molecules !== undefined && (
                        <Chip label={`${summary.unique_molecules} molecule(s)`} size="small" variant="outlined" />
                    )}
                    {summary.total_fragments !== undefined && (
                        <Chip label={`${summary.total_fragments} fragment(s)`} size="small" variant="outlined" />
                    )}
                </Stack>
            );

        case "generate_signatures":
            return (
                <Stack direction="row" spacing={1} flexWrap="wrap">
                    {summary.signatures !== undefined && (
                        <Chip label={`${summary.signatures} signature(s)`} size="small" variant="outlined" />
                    )}
                </Stack>
            );

        case "identify_molecules":
            // No count available from backend, show nothing
            return null;

        case "verify_results":
            // No count available from backend, show nothing
            return null;

        case "export_results":
            return (
                <Stack direction="row" spacing={1} flexWrap="wrap">
                    {summary.files_exported !== undefined && (
                        <Chip label={`${summary.files_exported} file(s) exported`} size="small" variant="outlined" />
                    )}
                </Stack>
            );

        default:
            return null;
    }
};

const StepCard: React.FC<StepCardProps> = ({
    task,
    isLast,
    isActive,
    summaryContent,
    onSelectTab,
}) => {
    const status = task.status;
    const isCompleted = status === "success" || status === "failed" || status === "warning" || status === "cancelled" || status === "skipped";
    const isClickable = isCompleted && onSelectTab;

    const duration = formatDuration(task.started_at, task.finished_at);

    return (
        <Box
            sx={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                position: "relative",
                pl: 3,
                pr: 2,
                py: 2,
            }}
        >
            {/* Timeline connector line */}
            {!isLast && (
                <Box
                    sx={{
                        position: "absolute",
                        left: "11px",
                        top: "40px",
                        bottom: "-16px",
                        width: "2px",
                        backgroundColor: isActive ? "primary.main" : "grey.300",
                        opacity: isActive ? 1 : 0.5,
                    }}
                />
            )}

            {/* Status icon */}
            <Box
                sx={{
                    position: "absolute",
                    left: 0,
                    top: 16,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 24,
                    height: 24,
                    borderRadius: "50%",
                    backgroundColor: "background.paper",
                    border: "2px solid",
                    borderColor: isActive ? "primary.main" : "grey.300",
                    zIndex: 1,
                }}
            >
                {getStatusIcon(status)}
            </Box>

            {/* Card content */}
            <Paper
                variant="outlined"
                onClick={isClickable ? onSelectTab : undefined}
                sx={{
                    width: "100%",
                    p: 2,
                    ml: 1,
                    cursor: isClickable ? "pointer" : "default",
                    backgroundColor: isActive ? alpha("#1976d2", 0.04) : "background.paper",
                    borderColor: isActive ? "primary.main" : "divider",
                    borderWidth: isActive ? 2 : 1,
                    transition: "all 0.2s ease-in-out",
                    "&:hover": isClickable
                        ? {
                              boxShadow: 3,
                              borderColor: "primary.main",
                              transform: "translateY(-1px)",
                          }
                        : {},
                }}
            >
                <Stack spacing={1}>
                    {/* Header row */}
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                        <Typography variant="subtitle1" fontWeight="600">
                            {task.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                            {getStatusLabel(status, isActive)}
                        </Typography>
                    </Stack>

                    {/* Timestamps and duration */}
                    {(task.started_at || task.finished_at || duration) && (
                        <Stack direction="row" spacing={2} alignItems="center">
                            {task.started_at && (
                                <Typography variant="caption" color="text.secondary">
                                    Started: {formatTime(task.started_at)}
                                </Typography>
                            )}
                            {task.finished_at && (
                                <Typography variant="caption" color="text.secondary">
                                    Finished: {formatTime(task.finished_at)}
                                </Typography>
                            )}
                            {duration && (
                                <Chip
                                    label={`Duration: ${duration}`}
                                    size="small"
                                    color={status === "success" ? "success" : "default"}
                                    variant="outlined"
                                />
                            )}
                        </Stack>
                    )}

                    {/* Summary content */}
                    {status === "success" && (summaryContent || getSummaryForTask(task)) && (
                        <Box sx={{ mt: 1 }}>
                            {summaryContent || getSummaryForTask(task)}
                        </Box>
                    )}

                    {/* Running indicator */}
                    {isActive && status === "running" && (
                        <Typography variant="caption" color="primary" sx={{ mt: 1 }}>
                            Processing...
                        </Typography>
                    )}
                </Stack>
            </Paper>
        </Box>
    );
};

export default StepCard;
