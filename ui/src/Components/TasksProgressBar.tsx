import { Box, Tooltip, Typography, CircularProgress } from "@mui/material";
import { CheckCircle, Error as ErrorIcon, Help as HelpIcon, Warning } from "@mui/icons-material";
import { FC, JSX } from "react";

export type TaskStatus = "unknown" | "ok" | "failed" | "inprogress" | "warning";

export interface TaskInfo {
    task_id: string;
    name: string;
    status: string;
    started_at?: string | null;
    finished_at?: string | null;
    summary?: Record<string, any>;
    artifacts?: string[];
}

interface TasksProgressBarProps {
    tasks: TaskInfo[];
}

const statusColor: Record<TaskStatus, string> = {
    unknown: "#9e9e9e",
    ok: "#4caf50",
    failed: "#f44336",
    inprogress: "#2196f3",
    warning: "#ff9800"
};

const statusIcon: Record<TaskStatus, JSX.Element> = {
    unknown: <HelpIcon sx={{ color: statusColor.unknown, fontSize: "2.5rem" }} />,
    ok: <CheckCircle sx={{ color: statusColor.ok, fontSize: "2.5rem" }} />,
    failed: <ErrorIcon sx={{ color: statusColor.failed, fontSize: "2.5rem" }} />,
    inprogress: <CircularProgress size={32} sx={{ color: statusColor.inprogress }} />,
    warning: <Warning sx={{ color: statusColor.warning, fontSize: "2.5rem" }} />,
};

const TASK_STEPS = [
    { key: "Load Simulation", keywords: ["load", "simulation"] },
    { key: "Resolve Signatures", keywords: ["signature", "fragment"] },
    { key: "Resolve Identifiers", keywords: ["identify", "identifier", "resolve"] },
    { key: "Summarize Results", keywords: ["summarize", "verify"] },
    { key: "Annotation Complete", keywords: ["complete", "export", "annotation"] },
];

function getStepForTask(taskName: string): string {
    const nameLower = taskName.toLowerCase();
    for (const step of TASK_STEPS) {
        if (step.keywords.some(kw => nameLower.includes(kw))) {
            return step.key;
        }
    }
    return "Unknown";
}

function getStepIndex(stepKey: string): number {
    return TASK_STEPS.findIndex(s => s.key === stepKey);
}

function deriveStepStatus(tasks: TaskInfo[], stepKey: string): TaskStatus {
    const matchingTasks = tasks.filter(t => getStepForTask(t.name) === stepKey);
    
    if (matchingTasks.length === 0) {
        const hasFailedTasks = tasks.some(t => t.status === "failed");
        const allTasksFinished = tasks.every(t => t.status !== "pending" && t.status !== "running");
        
        if (!hasFailedTasks && tasks.length > 0 && allTasksFinished) {
            return "ok";
        }
        
        // Check if there are no failed tasks anywhere
        const hasActiveTasks = tasks.some(t => t.status === "success" || t.status === "running" || t.status === "warning");
        
        if (!hasFailedTasks && hasActiveTasks) {
            // Determine "latest active step index"
            const latestActiveStepIndex = tasks
                .filter(t => t.status === "success" || t.status === "running" || t.status === "warning")
                .reduce((maxIdx, t) => {
                    const idx = getStepIndex(getStepForTask(t.name));
                    return idx > maxIdx ? idx : maxIdx;
                }, -1);
            
            const currentStepIndex = getStepIndex(stepKey);
            
            // If current step appears before or at the latest active step, return "inprogress"
            if (currentStepIndex <= latestActiveStepIndex) {
                return "inprogress";
            }
        }
        return "unknown";
    }
    
    if (matchingTasks.some(t => t.status === "failed")) {
        return "failed";
    }
    
    if (matchingTasks.some(t => t.status === "running")) {
        return "inprogress";
    }
    
    if (matchingTasks.some(t => t.status === "warning")) {
        return "warning";
    }
    
    if (matchingTasks.some(t => t.status === "success" || t.status === "skipped")) {
        return "ok";
    }
    
    return "unknown";
}

const TasksProgressBar: FC<TasksProgressBarProps> = ({ tasks }) => {
    const steps = TASK_STEPS.map(step => ({
        key: step.key,
        status: deriveStepStatus(tasks, step.key),
    }));

    const getLineColor = (index: number) => {
        // Simply return the color based on the step's status
        const stepStatus = steps[index].status;
        return statusColor[stepStatus];
    };

    return (
        <Box sx={{ display: "flex", alignItems: "center", width: "100%", overflowX: "auto", pb: 2 }}>
            {steps.map((step, index) => {
                return (
                    <Box
                        key={step.key}
                        sx={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            flex: 1,
                            minWidth: 0,
                            px: 1,
                            py: 2,
                            borderRadius: 2,
                        }}
                    >
                        <Tooltip
                            title={
                                <Box>
                                    <Typography variant="body1">{step.key}</Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        Status: {step.status}
                                    </Typography>
                                </Box>
                            }
                            arrow
                        >
                            <Box
                                sx={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    width: "100%",
                                    py: 3,
                                }}
                            >
                                {statusIcon[step.status]}
                            </Box>
                        </Tooltip>

                        <Typography
                            variant="h6"
                            sx={{
                                mt: 1,
                                whiteSpace: "pre-line",
                                userSelect: "none",
                                color: "text.primary",
                                textAlign: "center",
                                fontWeight: 500,
                            }}
                        >
                            {step.key}
                        </Typography>

                        {index < steps.length - 1 && (
                            <Box
                                sx={{
                                    height: "4px",
                                    width: "100%",
                                    backgroundColor: getLineColor(index),
                                    mt: 2,
                                    borderRadius: "3px",
                                }}
                            />
                        )}
                    </Box>
                );
            })}
        </Box>
    );
};

export default TasksProgressBar;
