import React, { useEffect, useRef, useState } from "react";
import {
    Box,
    Stack,
    Button,
    Typography,
    Paper,
    alpha,
    IconButton,
    Tooltip,
    Collapse,
    CircularProgress,
    Chip,
} from "@mui/material";
import {
    Stop as StopIcon,
    ExpandMore,
    ExpandLess,
    AccessTime,
    CheckCircle as CheckCircleIcon,
    Error as ErrorIcon,
    Warning as WarningIcon,
    Block as BlockIcon,
    RemoveCircle as RemoveCircleIcon,
    Pending as PendingIcon,
} from "@mui/icons-material";
import StepCard from "./StepCard";
import { TaskInfo, PipelineStatus } from "../hooks/useSmartPolling";

// Define the 8 pipeline steps in order (matching backend pipeline order)
export const PIPELINE_STEPS: Array<{ id: string; name: string }> = [
    { id: "discover_input", name: "Discover Input" },
    { id: "load_simulation", name: "Load Simulation" },
    { id: "repair_topology", name: "Repair Topology" },
    { id: "analyze_universe", name: "Analyze Universe" },
    { id: "generate_signatures", name: "Generate Signatures" },
    { id: "identify_molecules", name: "Identify Molecules" },
    { id: "verify_results", name: "Verify Results" },
    { id: "export_results", name: "Export Results" },
];

interface RunTimelineProps {
    tasks: TaskInfo[];
    pipeline: PipelineStatus;
    cancelRun?: () => Promise<void>;
    cancelLoading?: boolean;
    onSelectTab?: (tab: string) => void;
    defaultExpanded?: boolean;
}

// Helper to format duration from timestamps
const formatDuration = (startedAt: string | null | undefined, finishedAt?: string | null): string => {
    const start = startedAt ? new Date(startedAt) : null;
    const end = finishedAt ? new Date(finishedAt) : null;
    const now = new Date();
    
    // Use finished time if available, otherwise now
    const endTime = end || now;
    
    if (!start) return "0s";
    
    const diffMs = endTime.getTime() - start.getTime();
    if (diffMs < 1000) return "<1s";
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return `${diffSec}s`;
    const diffMin = Math.floor(diffSec / 60);
    const remainingSec = diffSec % 60;
    return `${diffMin}m ${remainingSec}s`;
};

// Get status label for a step (short version for compact bar)
const getStepStatusLabelShort = (status: string, isActive: boolean): string => {
    if (isActive && status === "running") return "Running…";
    switch (status) {
        case "success": return "Done";
        case "failed": return "Failed";
        case "warning": return "Warning";
        case "running": return "Running";
        case "cancelled": return "Cancelled";
        case "skipped": return "Skipped";
        case "pending":
        default:
            return "Waiting…";
    }
};

// Get status icon component for a step
const getStatusIcon = (status: string) => {
    switch (status) {
        case "success":
            return (
                <Box sx={{ width: 24, height: 24, borderRadius: "50%", backgroundColor: "success.main", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <CheckCircleIcon sx={{ fontSize: 16, color: "white" }} />
                </Box>
            );
        case "failed":
            return (
                <Box sx={{ width: 24, height: 24, borderRadius: "50%", backgroundColor: "error.main", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <ErrorIcon sx={{ fontSize: 16, color: "white" }} />
                </Box>
            );
        case "warning":
            return (
                <Box sx={{ width: 24, height: 24, borderRadius: "50%", backgroundColor: "warning.main", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <WarningIcon sx={{ fontSize: 16, color: "white" }} />
                </Box>
            );
        case "running":
            return <CircularProgress size={24} thickness={5} />;
        case "cancelled":
            return (
                <Box sx={{ width: 24, height: 24, borderRadius: "50%", backgroundColor: "text.disabled", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <BlockIcon sx={{ fontSize: 16, color: "white" }} />
                </Box>
            );
        case "skipped":
            return (
                <Box sx={{ width: 24, height: 24, borderRadius: "50%", backgroundColor: "text.disabled", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <RemoveCircleIcon sx={{ fontSize: 16, color: "white" }} />
                </Box>
            );
        case "pending":
        default:
            return (
                <Box sx={{ width: 24, height: 24, borderRadius: "50%", backgroundColor: "grey.200", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <PendingIcon sx={{ fontSize: 16, color: "text.disabled" }} />
                </Box>
            );
    }
};

const RunTimeline: React.FC<RunTimelineProps> = ({
    tasks,
    pipeline,
    cancelRun,
    cancelLoading = false,
    onSelectTab,
    defaultExpanded = false,
}) => {
    const [expanded, setExpanded] = useState(defaultExpanded);
    const activeStepRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // Find the active step index
    const activeStepIndex = PIPELINE_STEPS.findIndex((step) => {
        const task = tasks.find((t) => t.task_id === step.id);
        return task?.status === "running";
    });

    // Auto-scroll to active step when expanded and active step changes
    useEffect(() => {
        if (expanded && activeStepRef.current && containerRef.current) {
            const container = containerRef.current;
            const element = activeStepRef.current;
            
            // Calculate scroll position to center the active element
            const containerRect = container.getBoundingClientRect();
            const elementRect = element.getBoundingClientRect();
            
            // Scroll to center the element vertically
            const scrollTop = element.offsetTop - containerRect.height / 2 + elementRect.height / 2;
            
            container.scrollTo({
                top: Math.max(0, scrollTop),
                behavior: "smooth",
            });
        }
    }, [activeStepIndex, expanded]);

    // Auto-expand on failure or cancellation
    useEffect(() => {
        const hasFailed = tasks.some((t) => t.status === "failed");
        if (hasFailed || pipeline.status === "cancelled") {
            setExpanded(true);
        }
    }, [tasks, pipeline.status]);

    // Determine if cancel button should be shown
    const showCancelButton = pipeline.status === "running" || pipeline.status === "queued";
    const isTerminal = ["success", "failed", "cancelled"].includes(pipeline.status);

    // Get task for a step
    const getTaskForStep = (stepId: string): TaskInfo | undefined => {
        return tasks.find((t) => t.task_id === stepId);
    };

    // Handle tab selection for completed steps
    const handleStepClick = (stepId: string) => {
        if (!onSelectTab) return;
        
        // Map step IDs to tabs
        const stepToTab: Record<string, string> = {
            load_simulation: "loading",
            analyze_universe: "overview",
            generate_signatures: "signatures",
            identify_molecules: "overview",
            verify_results: "verification",
        };
        
        const tab = stepToTab[stepId];
        if (tab) {
            onSelectTab(tab);
        }
    };

    // Toggle expand/collapse
    const handleToggleExpand = () => {
        setExpanded((prev) => !prev);
    };

    // Handle cancel with stop propagation
    const handleCancel = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (cancelRun) {
            cancelRun();
        }
    };

    // Compute display step for compact bar
    // Priority: 1) running step, 2) most recently finished step, 3) first pending step
    const getDisplayStep = () => {
        // If there's a running step, use it
        if (activeStepIndex >= 0) {
            const task = getTaskForStep(PIPELINE_STEPS[activeStepIndex].id);
            return {
                index: activeStepIndex,
                step: PIPELINE_STEPS[activeStepIndex],
                task,
                status: task?.status || "pending",
            };
        }

        // Find the most recently finished step among tasks with terminal statuses
        const finishedStatuses = ["success", "failed", "warning", "skipped", "cancelled"] as const;
        let latestFinishedIndex = -1;
        let latestFinishedTask: TaskInfo | null = null;
        let latestFinishedTime: Date | null = null;

        for (let i = 0; i < PIPELINE_STEPS.length; i++) {
            const step = PIPELINE_STEPS[i];
            const task = getTaskForStep(step.id);
            if (task && finishedStatuses.includes(task.status as typeof finishedStatuses[number]) && task.finished_at) {
                const finishedTime = new Date(task.finished_at);
                if (!latestFinishedTime || finishedTime > latestFinishedTime) {
                    latestFinishedTime = finishedTime;
                    latestFinishedIndex = i;
                    latestFinishedTask = task;
                }
            }
        }

        if (latestFinishedIndex >= 0 && latestFinishedTask) {
            return {
                index: latestFinishedIndex,
                step: PIPELINE_STEPS[latestFinishedIndex],
                task: latestFinishedTask,
                status: latestFinishedTask.status,
            };
        }

        // Fall back to first pending step (e.g., queued run with no started tasks)
        const firstPendingTask = tasks.find((t) => t.status === "pending");
        if (firstPendingTask) {
            const pendingIndex = PIPELINE_STEPS.findIndex((s) => s.id === firstPendingTask.task_id);
            if (pendingIndex >= 0) {
                return {
                    index: pendingIndex,
                    step: PIPELINE_STEPS[pendingIndex],
                    task: firstPendingTask,
                    status: "pending",
                };
            }
        }

        // Ultimate fallback: first step as pending
        return {
            index: 0,
            step: PIPELINE_STEPS[0],
            task: undefined,
            status: "pending",
        };
    };

    const displayStep = getDisplayStep();
    const displayTask = displayStep.task;

    // Calculate elapsed time for display step or total run
    let elapsedTime = "0s";
    if (displayTask?.started_at) {
        elapsedTime = formatDuration(displayTask.started_at, isTerminal ? pipeline.finished_at : null);
    } else if (pipeline.started_at) {
        elapsedTime = formatDuration(pipeline.started_at, pipeline.finished_at);
    }

    // Get status for compact bar
    const compactStatus = displayTask?.status || pipeline.status;
    const compactStatusLabel = displayTask && displayStep.status !== "pending"
        ? getStepStatusLabelShort(displayTask.status, false)
        : displayStep.status === "pending" && !displayTask?.started_at
        ? "Waiting…"
        : `Run ${pipeline.status}`;

    return (
        <Paper
            variant="outlined"
            sx={{
                mt: 1,
                mb: 1,
                overflow: "hidden",
            }}
        >
            {/* Compact header bar (always visible) - single line, ~40px */}
            <Box
                onClick={handleToggleExpand}
                sx={{
                    height: 40,
                    px: 2,
                    display: "flex",
                    alignItems: "center",
                    cursor: "pointer",
                    backgroundColor: alpha("#1976d2", 0.02),
                    borderTop: 1,
                    borderLeft: 1,
                    borderRight: 1,
                    borderColor: "divider",
                    "&:hover": {
                        backgroundColor: alpha("#1976d2", 0.06),
                    },
                }}
            >
                {/* Left: Status icon */}
                <Box sx={{ mr: 1.5 }}>
                    {getStatusIcon(compactStatus)}
                </Box>

                {/* Center: Single-line step info: "Step 5/8 · Generate Signatures · Running…" */}
                <Box sx={{ flexGrow: 1, minWidth: 0, display: "flex", alignItems: "center" }}>
                    <Typography variant="body2" color="text.secondary" noWrap sx={{ mr: 1 }}>
                        Step {displayStep.index + 1}/{PIPELINE_STEPS.length}
                    </Typography>
                    <Typography variant="body2" color="text.disabled" sx={{ mr: 1 }}>·</Typography>
                    <Typography variant="body2" fontWeight="600" noWrap sx={{ mr: 1 }}>
                        {displayStep.step.name}
                    </Typography>
                    <Typography variant="body2" color="text.disabled" sx={{ mr: 1 }}>·</Typography>
                    <Chip
                        label={compactStatusLabel}
                        size="small"
                        sx={{
                            height: 20,
                            fontSize: "0.7rem",
                            backgroundColor:
                                compactStatus === "success"
                                    ? alpha("#4caf50", 0.1)
                                    : compactStatus === "failed"
                                    ? alpha("#f44336", 0.1)
                                    : compactStatus === "running"
                                    ? alpha("#1976d2", 0.1)
                                    : alpha("#9e9e9e", 0.1),
                            color:
                                compactStatus === "success"
                                    ? "success.main"
                                    : compactStatus === "failed"
                                    ? "error.main"
                                    : compactStatus === "running"
                                    ? "primary.main"
                                    : "text.secondary",
                        }}
                    />
                </Box>

                {/* Right: Elapsed time and actions */}
                <Stack direction="row" alignItems="center" spacing={0.5}>
                    <Stack direction="row" alignItems="center" spacing={0.3} sx={{ mr: 0.5 }}>
                        <AccessTime fontSize="small" color="action" />
                        <Typography variant="caption" color="text.secondary" noWrap>
                            {elapsedTime}
                        </Typography>
                    </Stack>

                    {/* Cancel button */}
                    {showCancelButton && cancelRun && (
                        <Tooltip title="Cancel run">
                            <IconButton
                                size="small"
                                onClick={handleCancel}
                                disabled={cancelLoading}
                                sx={{
                                    color: "error.main",
                                    "&:hover": {
                                        backgroundColor: alpha("#f44336", 0.1),
                                    },
                                }}
                            >
                                <StopIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                    )}

                    {/* Expand/collapse toggle */}
                    <IconButton
                        size="small"
                        onClick={handleToggleExpand}
                        sx={{
                            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
                            transition: "transform 0.2s",
                        }}
                    >
                        <ExpandMore fontSize="small" />
                    </IconButton>
                </Stack>
            </Box>

            {/* Expanded panel with full timeline */}
            <Collapse in={expanded}>
                <Box sx={{ p: 2 }}>
                    {/* Collapse button at top of expanded panel */}
                    <Stack direction="row" justifyContent="flex-end" sx={{ mb: 1 }}>
                        <Button
                            size="small"
                            startIcon={<ExpandLess />}
                            onClick={handleToggleExpand}
                        >
                            Collapse
                        </Button>
                    </Stack>

                    {/* Status banner for terminal states */}
                    {isTerminal && (
                        <Box
                            sx={{
                                mb: 2,
                                p: 1.5,
                                borderRadius: 1,
                                backgroundColor:
                                    pipeline.status === "success"
                                        ? alpha("#4caf50", 0.1)
                                        : pipeline.status === "failed"
                                        ? alpha("#f44336", 0.1)
                                        : alpha("#9e9e9e", 0.1),
                                color:
                                    pipeline.status === "success"
                                        ? "success.main"
                                        : pipeline.status === "failed"
                                        ? "error.main"
                                        : "text.secondary",
                            }}
                        >
                            <Typography variant="body2" fontWeight="600" textTransform="capitalize">
                                Run {pipeline.status}
                            </Typography>
                        </Box>
                    )}

                    {/* Timeline */}
                    <Box
                        ref={containerRef}
                        sx={{
                            maxHeight: 600,
                            overflowY: "auto",
                            position: "relative",
                        }}
                    >
                        <Stack spacing={0}>
                            {PIPELINE_STEPS.map((step, index) => {
                                const task = getTaskForStep(step.id);
                                const isActive = index === activeStepIndex;
                                const isLast = index === PIPELINE_STEPS.length - 1;

                                // Create a placeholder task if none exists yet
                                const taskData: TaskInfo =
                                    task ||
                                    ({
                                        task_id: step.id,
                                        name: step.name,
                                        status: "pending",
                                        started_at: null,
                                        finished_at: null,
                                    } as TaskInfo);

                                return (
                                    <Box
                                        key={step.id}
                                        ref={isActive ? activeStepRef : null}
                                    >
                                        <StepCard
                                            task={taskData}
                                            isLast={isLast}
                                            isActive={isActive}
                                            onSelectTab={() => handleStepClick(step.id)}
                                        />
                                    </Box>
                                );
                            })}
                        </Stack>
                    </Box>
                </Box>
            </Collapse>
        </Paper>
    );
};

export default RunTimeline;
